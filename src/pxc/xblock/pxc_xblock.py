"""PXC XBlock — runs PXC activities inside Open edX.

Manifest parsing, capability/action/event validation, and WASM sandbox
execution live in the standalone pxc-libserver (see libserver_client.py) —
this xblock only talks HTTP to it. Field storage and file storage stay here
(internal_api.py), reached by the lib-server via callback.

Targets Python 3.5 / Django 2.2 (Juniper-era Open edX): no f-strings, no PEP
526 variable annotations, no bare generic subscripting, no
``from __future__ import annotations``, no ``importlib.resources.files``
(3.9+) — package resources are read via a plain ``__file__``-relative path
instead.
"""

import json
import logging
import os
from datetime import timedelta
from typing import Any, Dict, Optional, Tuple

from django.contrib.auth import get_user_model
from django.db.models import Max
from django.template import Context, Template
from django.utils import timezone

from web_fragments.fragment import Fragment
from webob import Response
from xblock.completable import CompletableXBlockMixin
from xblock.core import XBlock
from xblock.fields import Boolean, Float, Scope, String
from xblock.validation import Validation

from pxc.xblock import libserver_client
from pxc.xblock.field_store import DjangoFieldStore
from pxc.xblock.libserver_client import (
    ActionValidationError,
    ActivityNotFoundError,
    BuildFailedError,
    LibServerError,
    UploadValidationError,
)
from pxc.xblock.models import PendingEvent
from pxc.xblock.permission import Permission
from pxc.xblock.permissions import resolve_permission

logger = logging.getLogger(__name__)

_field_store = DjangoFieldStore()

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))

_PERM_RANK = {"view": 0, "play": 1, "edit": 2}

# Cross-user events are persisted in PendingEvent so polling clients can
# replay them with cursor-based catch-up. Anything older than this is unlikely
# to be useful and we drop it on every action handler call to keep the table
# bounded.
PENDING_EVENT_TTL = timedelta(hours=24)


def _event_visible(
    event_context, event_permission, course_id, activity_id, user_id, permission
):
    # type: (Dict[str, str], str, str, str, str, Permission) -> bool
    """Return True if this user/permission should receive the event."""
    if "user_id" in event_context and event_context["user_id"] != user_id:
        return False
    if "activity_id" in event_context and event_context["activity_id"] != activity_id:
        return False
    if "course_id" in event_context and event_context["course_id"] != course_id:
        return False
    return _PERM_RANK.get(permission.value, 0) >= _PERM_RANK.get(event_permission, 0)


def _json_response(data):
    # type: (Any) -> Response
    return Response(json.dumps(data), content_type="application/json", charset="utf8")


class PxcXBlock(CompletableXBlockMixin, XBlock):
    # CompletableXBlockMixin sets has_custom_completion=True and
    # completion_mode=COMPLETABLE — this tells the platform's own default
    # (view-based) completion inference to back off and defer entirely to
    # what this block reports itself. That declaration alone wasn't enough
    # to make `self.runtime.publish(self, "completion", ...)` actually reach
    # the completion app's receiver in this environment though (confirmed
    # 2026-07: checkmark stayed unmarked across repeated tests even with
    # this mixin in place) — see `_publish_grade_event` below, which calls
    # `BlockCompletion.objects.submit_completion(...)` / `SCORE_PUBLISHED`
    # directly instead of going through `publish()` for grade/completion.
    # Kept the mixin anyway: it's still the correct declaration of this
    # block's completion mode regardless of which mechanism records it.
    has_author_view = True

    display_name = String(
        display_name="Display Name",
        default="PXC Activity",
        scope=Scope.settings,
    )
    activity_slug = String(
        display_name="Activity",
        default="",
        scope=Scope.settings,
    )
    # A Field, not a plain class attribute — the LMS grading pipeline reads
    # `block.has_score` as an *instance* attribute, so making it a Boolean
    # field (like `weight` below) lets authors toggle it per-instance from
    # Studio instead of it being permanently on for every activity. Lets
    # activities publish real grades via report_scored/passed/failed (see
    # the "action" handler below and pxc.lib.runtime's report_* methods) —
    # when off, the LMS grading pipeline ignores "grade" publish events from
    # this block entirely (report_completed/report_progressed's completion
    # events are unaffected either way).
    has_score = Boolean(
        display_name="Scored",
        help="Whether this activity contributes a grade to the course. Turn "
        "off for activities that only use reportCompleted/reportProgressed "
        "(completion) or no grading at all.",
        default=True,
        scope=Scope.settings,
    )
    weight = Float(
        display_name="Problem Weight",
        help="Defines the number of points each problem is worth in this activity.",
        default=1.0,
        scope=Scope.settings,
    )

    # ------------------------------------------------------------------ #
    # Context helpers
    # ------------------------------------------------------------------ #

    def _get_ids(self):
        # type: () -> Tuple[str, str, str]
        """Return (course_id, activity_id, user_id)."""
        user_id = str(self.scope_ids.user_id)
        activity_id = str(self.scope_ids.usage_id)
        course_key = getattr(self.scope_ids.usage_id, "course_key", None)
        course_id = str(course_key) if course_key else ""
        return course_id, activity_id, user_id

    def _resolve_permission(self):
        # type: () -> Permission
        """Permission for this handler call, derived from XBlock runtime context."""
        # TODO how do we actually determine if a user is allowed to be in edit mode?
        # shouldn't it be getattr(self.runtime, "user_is_staff", False)? But this fails in studio view
        has_edit_permission = getattr(self.runtime, "is_author_mode", False)
        return resolve_permission(self.scope_ids.user_id, has_edit_permission)

    def _publish_grade_event(self, event_type, payload):
        # type: (str, Dict[str, Any]) -> None
        """Record a grade/completion event directly against edx-platform's
        own grading/completion primitives, instead of relying solely on
        ``self.runtime.publish(self, event_type, payload)``.

        Confirmed (2026-07) that `publish("completion", ...)` alone does not
        reliably reach the completion app's receiver in this environment,
        even with `CompletableXBlockMixin` correctly declared — the checkmark
        stayed unmarked across repeated tests. The platform team's own
        `publish_user_score`-style helper (used elsewhere for offline grade
        fixes) calls `SCORE_PUBLISHED` and `BlockCompletion.submit_completion`
        directly and is verified working here, so this mirrors that instead
        of trusting the `publish()` abstraction for these two event types.

        Imports are deferred and best-effort: `completion` / `lms.djangoapps`
        are edx-platform-internal packages not present outside a real LMS/CMS
        process (e.g. not in this project's own dev/test venv) — a failure
        to import is logged, not raised, so a misconfigured install doesn't
        turn a learner's submit into a 500.
        """
        user_id = self.scope_ids.user_id
        if user_id is None:
            logger.error("Cannot publish %s event: no user_id in this context", event_type)
            return
        usage_key = self.scope_ids.usage_id

        if event_type == "grade":
            try:
                from lms.djangoapps.grades.signals.signals import SCORE_PUBLISHED
            except ImportError:
                logger.exception(
                    "Could not import SCORE_PUBLISHED; grade not recorded for "
                    "user_id=%s usage_key=%s",
                    user_id,
                    usage_key,
                )
                return
            student = get_user_model().objects.get(pk=user_id)
            SCORE_PUBLISHED.send(
                sender=None,
                user=student,
                block=self,
                raw_earned=payload["value"],
                raw_possible=payload["max_value"],
                only_if_higher=False,
                score_deleted=False,
            )
        elif event_type == "completion":
            try:
                from completion import waffle as completion_waffle
                from completion.models import BlockCompletion
            except ImportError:
                logger.exception(
                    "Could not import completion app; completion not marked for "
                    "user_id=%s usage_key=%s",
                    user_id,
                    usage_key,
                )
                return
            if not completion_waffle.waffle().is_enabled(
                completion_waffle.ENABLE_COMPLETION_TRACKING
            ):
                return
            student = get_user_model().objects.get(pk=user_id)
            BlockCompletion.objects.submit_completion(
                user=student,
                block_key=usage_key,
                completion=payload["completion"],
            )
        else:
            logger.error("Unknown grade event_type: %s", event_type)

    def _is_superuser(self):
        # type: () -> bool
        """True only for Django superusers — deliberately stricter than
        course-staff/author permission. Used to gate activity upload+build
        (arbitrary Python source getting run through componentize-py),
        which is platform-wide risk, not a per-course-author one.

        Only reliable from inside a live handler call (action/save_settings/
        upload_activity), where scope_ids.user_id is the real, authenticated
        Django user id. Confirmed by diagnostic (2026-07): studio_view()'s
        render path carries no user context at all in this environment
        (scope_ids.user_id is None there, and `self.runtime.service(self,
        "user")` itself raises) — this is not a bug in this check, it's a
        constraint of the render path, so studio_view() must never rely on
        this to decide what to show. Fails closed (False) on any lookup
        error, e.g. anonymous/view-mode callers with no real user_id.
        """
        user_id = self.scope_ids.user_id
        if user_id is None:
            return False
        try:
            user = get_user_model().objects.get(pk=user_id)
        except Exception:
            logger.exception("Failed to resolve is_superuser for user_id=%s", user_id)
            return False
        return bool(user.is_superuser)

    @staticmethod
    def resource_string(path):
        # type: (str) -> str
        """Read a UTF-8 text resource bundled with this xblock."""
        full_path = os.path.join(_PACKAGE_DIR, path)
        with open(full_path, "rb") as f:
            return f.read().decode("utf-8")

    def _pxcjs_bundle(self):
        # type: () -> str
        """pxc.js + xblock_pxc.js concatenated as one non-module classic script.

        Both source files are ES modules; we strip the single `export class`
        keyword from each so PXC and XBlockPXC are top-level class
        declarations in the resulting script. Served via the `pxcjs` handler
        and loaded by the fragment with `add_javascript_url` — i.e. a real
        <script src="…"> tag, which puts the class bindings in the realm's
        global declarative record where the per-view init scripts
        (student.js / studio.js) can resolve them by bare name.

        pxc.js is a plain browser Web Component with no server-side
        coupling, so it's vendored directly under this package's static/js/
        rather than pulled from pxc-lib (which this xblock no longer depends
        on — see libserver_client.py).
        """
        base = self.resource_string("static/js/pxc.js").replace(
            "export class PXC ", "class PXC ", 1
        )
        sub = self.resource_string("static/js/xblock_pxc.js").replace(
            "export class XBlockPXC ", "class XBlockPXC ", 1
        )
        return "{0}\n{1}\n".format(base, sub)

    @staticmethod
    def _initial_events_cursor(course_id, activity_id):
        # type: (str, str) -> int
        """Current max PendingEvent.id for this activity, or 0 if no events yet.

        Embedded in the rendered fragment so first-time clients start polling
        from "now" instead of replaying the entire retention window.
        """
        agg = PendingEvent.objects.filter(
            course_id=course_id, activity_id=activity_id
        ).aggregate(m=Max("id"))
        return int(agg["m"] or 0)

    def _storage_base_url(self):
        # type: () -> str
        return self.runtime.handler_url(self, "storage").strip("?")

    def validate(self):
        # type: () -> Validation
        # Open edX's LmsBlockMixin.validate() calls resources.files('pxc') to
        # find translations, which crashes because 'pxc' is a namespace package
        # shared between pxc-lib and pxc-xblock. Skip to XBlock.validate() to
        # avoid the broken i18n service path; PXC has no validation requirements
        # that need translation-aware messages.
        return XBlock.validate(self)

    # ------------------------------------------------------------------ #
    # Views
    # ------------------------------------------------------------------ #

    def _attach_view_javascript(self, frag, view):
        # type: (Fragment, str) -> None
        """Wire the standard JS resources + initialize_js entrypoint for a view."""
        frag.add_javascript_url(self.runtime.handler_url(self, "pxcjs").strip("?"))
        frag.add_javascript(self.resource_string("static/js/{0}.js".format(view)))
        frag.initialize_js("Pxc{0}XBlock".format(view.capitalize()))

    def _render_pxc_activity(self, permission):
        # type: (Permission) -> str
        """Render the <pxc-activity> element via the shared partial template.

        Used by both student_view and author_view. Django's template engine
        auto-escapes every `{{ var }}` for HTML attribute / text context, so
        the embedded JSON (data-context, data-state) ends up with proper
        `&quot;` for its inner double quotes without any manual escaping.
        """
        course_id, activity_id, user_id = self._get_ids()
        state = libserver_client.get_state(
            self.activity_slug,
            activity_id=activity_id,
            course_id=course_id,
            user_id=user_id,
            permission=permission,
            storage_base_url=self._storage_base_url(),
        )
        ctx_json = json.dumps(
            {"activity_id": activity_id, "course_id": course_id, "user_id": user_id}
        )
        return self._render_template(
            "static/html/pxc_activity.html",
            {
                "ctx_json": ctx_json,
                "state_json": json.dumps(state),
                # Note that for some reason, in the studio the events url is
                # suffixed with a "?", which we strip
                "action_url": self.runtime.handler_url(self, "action").strip("?"),
                "events_url": self.runtime.handler_url(self, "events").strip("?"),
                "asset_base_url": self.runtime.handler_url(self, "asset").strip("?"),
                "src_url": self.runtime.handler_url(self, "uijs").strip("?"),
                "events_cursor": self._initial_events_cursor(course_id, activity_id),
                "permission": permission.value,
            },
        )

    def student_view(self, context=None):
        # type: (Optional[Dict[str, Any]]) -> Fragment
        if not self.activity_slug:
            return Fragment(
                "<p>PXC activity not configured. Open Studio to select an activity.</p>"
            )

        frag = Fragment(self._render_pxc_activity(Permission.play))
        self._attach_view_javascript(frag, "student")
        return frag

    def author_view(self, context=None):
        # type: (Optional[Dict[str, Any]]) -> Fragment
        # Studio's inline preview on the unit page. Without this, the runtime
        # falls back to student_view, which renders at `play` permission.
        if not self.activity_slug:
            return Fragment(
                "<p>PXC activity not configured. Click Edit to select an activity.</p>"
            )

        frag = Fragment(self._render_pxc_activity(Permission.edit))
        self._attach_view_javascript(frag, "student")
        return frag

    def studio_view(self, context=None):
        # type: (Optional[Dict[str, Any]]) -> Fragment
        try:
            activities = libserver_client.list_activities()
        except LibServerError:
            logger.exception("Failed to reach pxc-libserver for activity list")
            activities = []
        rendered = self._render_template(
            "static/html/studio_view.html",
            {
                "activities": activities,
                "current_slug": self.activity_slug,
                "display_name": self.display_name,
                "has_score": self.has_score,
                "weight": self.weight,
            },
        )
        frag = Fragment(rendered)
        self._attach_view_javascript(frag, "studio")
        return frag

    # ------------------------------------------------------------------ #
    # Handlers
    # ------------------------------------------------------------------ #

    @XBlock.handler
    def pxcjs(self, request, suffix=""):
        """Serve pxc.js + xblock_pxc.js as a single non-module classic script.

        Loaded by the views with `frag.add_javascript_url(...)`, which produces
        a real <script src="…"> tag and reliably exposes the class declarations
        to the per-view init scripts (see `_pxcjs_bundle`).
        """
        return Response(
            self._pxcjs_bundle(),
            content_type="application/javascript",
            charset="utf8",
        )

    @XBlock.handler
    def action(self, request, suffix=""):
        if not self.activity_slug:
            return _json_response({"events": [], "cursor": 0})

        try:
            # json.loads() only accepts bytes from Python 3.6+; decode explicitly
            # for Python 3.5 compat.
            body = json.loads(request.body.decode("utf-8"))
        except (ValueError, KeyError):
            return Response(status=400)

        name = str(body.get("name", ""))
        value = body.get("value", "")
        permission = self._resolve_permission()

        course_id, activity_id, user_id = self._get_ids()

        try:
            result = libserver_client.on_action(
                self.activity_slug,
                activity_id=activity_id,
                course_id=course_id,
                user_id=user_id,
                permission=permission,
                storage_base_url=self._storage_base_url(),
                name=name,
                value=value,
            )
        except ActionValidationError as e:
            return Response(str(e), status=400)
        except ActivityNotFoundError:
            return Response(status=404)

        # Record grading/completion signals directly (see
        # _publish_grade_event's docstring for why this bypasses
        # self.runtime.publish). This is the one bit that must happen here,
        # not in libserver: only this process has real Django/LMS context
        # (the authenticated user, the modulestore, the grades/completion
        # apps) tied to the current request.
        for grade in result["grades"]:
            self._publish_grade_event(grade["event_type"], grade["payload"])

        # Retention sweep: drop pending events that are too old to be useful.
        PendingEvent.objects.filter(
            created_at__lt=timezone.now() - PENDING_EVENT_TTL
        ).delete()

        caller_events = []
        last_id = 0

        for ev in result["events"]:
            ctx = ev["context"]
            pe = PendingEvent.objects.create(
                course_id=course_id,
                activity_id=activity_id,
                event_name=ev["name"],
                event_value=ev["value"],
                event_context=json.dumps(ctx),
                event_permission=ev["permission"],
            )
            assert pe.id is not None
            last_id = pe.id
            if _event_visible(
                ctx, ev["permission"], course_id, activity_id, user_id, permission
            ):
                caller_events.append({"name": ev["name"], "value": ev["value"]})

        return _json_response({"events": caller_events, "cursor": last_id})

    @XBlock.handler
    def events(self, request, suffix=""):
        """Return buffered events since a cursor for cross-user polling."""
        course_id, activity_id, user_id = self._get_ids()
        permission = self._resolve_permission()

        # `since` is mandatory: a missing/invalid cursor would return every
        # event in the (24h-retention-bounded) PendingEvent table on every
        # poll, which we don't want clients to default into by accident.
        since_raw = request.GET.get("since")
        if since_raw is None:
            return Response("Missing `since` query parameter", status=400)
        try:
            since = int(since_raw)
        except ValueError:
            return Response("Invalid `since` query parameter", status=400)

        rows = PendingEvent.objects.filter(
            course_id=course_id,
            activity_id=activity_id,
            id__gt=since,
        ).order_by("id")

        result = []
        cursor = since
        for row in rows:
            assert row.id is not None
            cursor = row.id  # advance cursor even for filtered-out events
            ctx = json.loads(row.event_context)
            if _event_visible(
                ctx, row.event_permission, course_id, activity_id, user_id, permission
            ):
                result.append({"name": row.event_name, "value": row.event_value})

        return _json_response({"events": result, "cursor": cursor})

    @XBlock.handler
    def asset(self, request, suffix=""):
        """Serve a manifest-declared activity asset (proxied from pxc-libserver)."""
        if not self.activity_slug:
            return Response(status=404)
        course_id, activity_id, user_id = self._get_ids()
        try:
            content, content_type = libserver_client.get_asset(
                self.activity_slug,
                suffix.lstrip("/"),
                activity_id=activity_id,
                course_id=course_id,
                user_id=user_id,
            )
        except ActivityNotFoundError:
            return Response(status=404)
        return Response(content, content_type=content_type)

    @XBlock.handler
    def storage(self, request, suffix=""):
        """Serve a file from activity storage (proxied from pxc-libserver).

        URL shape (matches the `storage_url` a sandbox script requests):
            <handler>/<storage_name>/<file_path>[?activity_id=&course_id=&user_id=]
        Query params let an activity read another scope's file (e.g. an
        instructor reading a learner's submission) — they're forwarded as a
        context override so the lib-server rebuilds the same scoped path.
        """
        if not self.activity_slug:
            return Response(status=404)
        clean = suffix.lstrip("/")
        storage_name, _, file_path = clean.partition("/")
        if not storage_name:
            return Response(status=404)
        context_override = None
        activity_id_override = request.GET.get("activity_id")
        course_id_override = request.GET.get("course_id")
        user_id_override = request.GET.get("user_id")
        if activity_id_override or course_id_override or user_id_override:
            context_override = {
                "activity-id": activity_id_override,
                "course-id": course_id_override,
                "user-id": user_id_override,
            }
        course_id, activity_id, user_id = self._get_ids()
        try:
            content, content_type = libserver_client.storage_read(
                self.activity_slug,
                activity_id=activity_id,
                course_id=course_id,
                user_id=user_id,
                name=storage_name,
                path=file_path,
                context_override=context_override,
            )
        except ActivityNotFoundError:
            return Response(status=404)
        return Response(content, content_type=content_type)

    @XBlock.handler
    def uijs(self, request, suffix=""):
        """Serve the activity's ui.js entry point as an ES module (proxied).

        Targeted by data-src on <pxc-activity>; pxc.js dynamically imports it
        and calls its setup(activity) export. The ui.js entry isn't part of
        the manifest's `assets` list — it's the special `manifest.ui` path —
        so it gets its own handler instead of going through `asset`.
        """
        if not self.activity_slug:
            return Response(status=404)
        course_id, activity_id, user_id = self._get_ids()
        try:
            content, content_type = libserver_client.get_ui(
                self.activity_slug,
                activity_id=activity_id,
                course_id=course_id,
                user_id=user_id,
            )
        except ActivityNotFoundError:
            return Response(status=404)
        return Response(content, content_type=content_type, charset="utf8")

    @XBlock.handler
    def save_settings(self, request, suffix=""):
        """Save studio settings (activity slug, display name, grading)."""
        try:
            body = json.loads(request.body.decode("utf-8"))
        except ValueError:
            return Response(status=400)
        slug = str(body.get("activity_slug", "")).strip()
        try:
            known_activities = libserver_client.list_activities()
        except LibServerError:
            logger.exception("Failed to reach pxc-libserver for activity list")
            return Response("PXC lib-server unavailable", status=502)
        if slug and slug not in known_activities:
            return Response("Unknown activity", status=400)
        display_name = str(body.get("display_name", "")).strip()
        self.activity_slug = slug
        if display_name:
            self.display_name = display_name
        if "has_score" in body:
            self.has_score = bool(body["has_score"])
        if "weight" in body:
            try:
                self.weight = float(body["weight"])
            except (TypeError, ValueError):
                return Response("Invalid weight", status=400)
        self.save()
        return _json_response({"ok": True})

    @XBlock.handler
    def reset_learner(self, request, suffix=""):
        """Delete one learner's stored field/log data for this activity instance.

        Studio-only remediation (e.g. "let this student retry their scored
        activity"), not a general data-deletion tool: it only clears rows
        this xblock itself wrote via internal_api (scenario, prompt, output,
        attempts, grade_result, submitted, ...) for the given user on this
        specific block — see field_store.reset_learner. It does NOT touch:

        - course/activity/global-scoped fields (e.g. the shared
          haiku_api_key configured via credentials.save)
        - the LMS's own grade/completion record for this student. That lives
          in Open edX's own StudentModule/grades tables, set by the earlier
          `self.runtime.publish(self, "grade"/"completion", ...)` call in the
          `action` handler — clearing PXC's own fields doesn't undo it. Use
          the platform's own "Reset Student Attempts" / grade override tools
          for that, in addition to this, if the activity is scored.

        Same trust level as save_settings: reachable only through Studio,
        which already gates access to course staff before this handler is
        ever called — no extra permission check here (unlike upload_activity,
        which guards against a stronger, platform-wide risk).
        """
        if not self.activity_slug:
            return Response("No activity configured on this block", status=400)
        try:
            body = json.loads(request.body.decode("utf-8"))
        except ValueError:
            return Response(status=400)
        email = str(body.get("email", "")).strip()
        if not email:
            return Response("Missing 'email'", status=400)

        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email)
        except user_model.DoesNotExist:
            return Response("No user found with that email", status=404)
        except user_model.MultipleObjectsReturned:
            return Response("Multiple users match that email", status=409)

        course_id, activity_id, _ = self._get_ids()
        result = _field_store.reset_learner(
            course_id, self.activity_slug, activity_id, str(user.pk)
        )
        return _json_response(
            {
                "ok": True,
                "username": user.username,
                "fields_deleted": result["fields_deleted"],
                "log_entries_deleted": result["log_entries_deleted"],
            }
        )

    @XBlock.handler
    def upload_activity(self, request, suffix=""):
        """Upload a new activity bundle (zip) — superusers only.

        Deliberately stricter than course-author permission: this can run
        arbitrary Python source through componentize-py (when server-side
        building is enabled on pxc-libserver — see PXC_ENABLE_ACTIVITY_BUILD
        in its config), which is a platform-wide risk, not a per-course one.

        The enforcement lives entirely here, not in studio_view() — that
        render path carries no user context in this environment (confirmed
        by diagnostic; see _is_superuser()'s docstring), so the upload
        widget is unconditionally visible to anyone who can open Studio's
        edit view. Non-superusers get a clean 403 on submit instead of the
        widget being hidden. This handler IS a live authenticated request
        (same as action/save_settings), so scope_ids.user_id is reliable here.

        Proxies straight to pxc-libserver's /activities/upload, which
        validates the manifest, builds an uncompiled Python sandbox via
        componentize-py if one is present and server-side building is
        enabled (no build support for JS sandboxes regardless — those must
        be pre-built and included as sandbox.wasm already; see
        pxc.libserver.upload's docstring), and installs it under its
        manifest-declared slug.
        """
        if not self._is_superuser():
            return Response("Only platform superusers can upload activities", status=403)
        upload = request.POST.get("bundle")
        if upload is None or not getattr(upload, "file", None):
            return Response("Missing 'bundle' file field", status=400)
        zip_bytes = upload.file.read()
        try:
            slug = libserver_client.upload_activity(
                zip_bytes, upload.filename or "bundle.zip"
            )
        except UploadValidationError as e:
            return Response(str(e), status=400)
        except BuildFailedError as e:
            return Response(str(e), status=422)
        except LibServerError:
            logger.exception("Failed to reach pxc-libserver for activity upload")
            return Response("PXC lib-server unavailable", status=502)
        return _json_response({"slug": slug})

    # ------------------------------------------------------------------ #
    # Template helper
    # ------------------------------------------------------------------ #

    def _render_template(self, path, ctx):
        # type: (str, Dict[str, Any]) -> str
        """Render an HTML template bundled with this xblock through Django.

        Django auto-escapes `{{ var }}` for HTML attribute / text contexts —
        callers should NOT pre-escape values. Use `{{ var|safe }}` in the
        template body to opt out for raw-HTML fragments built upstream
        (e.g. `activity_options`, the rendered `<pxc-activity>` partial).
        """
        return str(Template(self.resource_string(path)).render(Context(ctx)))
