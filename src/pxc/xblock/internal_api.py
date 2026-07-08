"""Internal callback API for the standalone PXC lib-server.

The lib-server hosts `ActivityRuntime` + the wasmtime sandbox in its own
process (it needs a newer Python than this LMS/CMS install). Field storage
and file storage stay here — this module is what its `HttpFieldStore` /
`HttpFileStorage` adapters call back into over HTTP, reusing the existing
Django-backed `DjangoFieldStore` / `DjangoFileStorage` unchanged.

Not part of the XBlock handler mechanism (there's no XBlock usage/runtime
context here — every request carries plain scalar identifiers) — this is a
small plugin Django app wired up via `PxcXBlockConfig.plugin_app` (see
apps.py), reachable at `/pxc/internal/...` in both LMS and CMS.

Every view is guarded by `require_internal_secret`, matching a shared secret
configured on both sides (`PXC_INTERNAL_SECRET`). This is a private,
service-to-service channel — it must never be reachable from a browser.

Targets Python 3.5 (Juniper-era Open edX): no f-strings, no
``from __future__ import annotations``, no bare generic subscripting.
"""

import base64
import functools
import hmac
import json
from typing import Any, Callable, Dict

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from pxc.xblock.field_store import DjangoFieldStore
from pxc.xblock.file_storage import DjangoFileStorage, FileStorageError

_field_store = DjangoFieldStore()


def require_internal_secret(view):
    # type: (Callable[..., HttpResponse]) -> Callable[..., HttpResponse]
    @functools.wraps(view)
    def wrapped(request, *args, **kwargs):
        expected = getattr(settings, "PXC_INTERNAL_SECRET", "")
        got = request.headers.get("X-PXC-Internal-Secret", "")
        if not expected or not hmac.compare_digest(got, expected):
            return HttpResponse(status=401)
        return view(request, *args, **kwargs)

    return wrapped


def _body(request):
    # type: (HttpRequest) -> Dict[str, Any]
    # json.loads() only accepts bytes directly from Python 3.6+; decode
    # explicitly so this works on Python 3.5 too.
    return json.loads(request.body.decode("utf-8"))


# ------------------------------------------------------------------ #
# Fields
# ------------------------------------------------------------------ #


@csrf_exempt
@require_POST
@require_internal_secret
def fields_get(request):
    b = _body(request)
    value = _field_store.get(
        b["course_id"], b["activity_name"], b["activity_id"], b["user_id"], b["key"]
    )
    return JsonResponse({"value": value})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_set(request):
    b = _body(request)
    _field_store.set(
        b["course_id"],
        b["activity_name"],
        b["activity_id"],
        b["user_id"],
        b["key"],
        b["value"],
    )
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_delete(request):
    b = _body(request)
    deleted = _field_store.delete(
        b["course_id"], b["activity_name"], b["activity_id"], b["user_id"], b["key"]
    )
    return JsonResponse({"deleted": deleted})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_log_get(request):
    b = _body(request)
    value = _field_store.log_get(
        b["course_id"],
        b["activity_name"],
        b["activity_id"],
        b["user_id"],
        b["key"],
        b["entry_id"],
    )
    return JsonResponse({"value": value})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_log_get_after(request):
    b = _body(request)
    entries = _field_store.log_get_after(
        b["course_id"],
        b["activity_name"],
        b["activity_id"],
        b["user_id"],
        b["key"],
        b["after_id"],
        b["count"],
    )
    return JsonResponse({"entries": entries})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_log_get_before(request):
    b = _body(request)
    entries = _field_store.log_get_before(
        b["course_id"],
        b["activity_name"],
        b["activity_id"],
        b["user_id"],
        b["key"],
        b["before_id"],
        b["count"],
    )
    return JsonResponse({"entries": entries})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_log_append(request):
    b = _body(request)
    entry_id = _field_store.log_append(
        b["course_id"],
        b["activity_name"],
        b["activity_id"],
        b["user_id"],
        b["key"],
        b["value"],
    )
    return JsonResponse({"id": entry_id})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_log_delete(request):
    b = _body(request)
    deleted = _field_store.log_delete(
        b["course_id"],
        b["activity_name"],
        b["activity_id"],
        b["user_id"],
        b["key"],
        b["entry_id"],
    )
    return JsonResponse({"deleted": deleted})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_log_delete_before(request):
    b = _body(request)
    deleted = _field_store.log_delete_before(
        b["course_id"],
        b["activity_name"],
        b["activity_id"],
        b["user_id"],
        b["key"],
        b["before_id"],
    )
    return JsonResponse({"deleted": deleted})


@csrf_exempt
@require_POST
@require_internal_secret
def fields_log_clear(request):
    b = _body(request)
    deleted = _field_store.log_clear(
        b["course_id"], b["activity_name"], b["activity_id"], b["user_id"], b["key"]
    )
    return JsonResponse({"deleted": deleted})


# ------------------------------------------------------------------ #
# Storage
# ------------------------------------------------------------------ #


def _storage_for(activity_id):
    # type: (str) -> DjangoFileStorage
    return DjangoFileStorage("pxc/{0}/storage".format(activity_id))


@csrf_exempt
@require_POST
@require_internal_secret
def storage_read(request):
    b = _body(request)
    try:
        content = _storage_for(b["activity_id"]).read(b["path"])
    except FileStorageError as e:
        return JsonResponse({"detail": str(e)}, status=404)
    return JsonResponse({"content_b64": base64.b64encode(content).decode("ascii")})


@csrf_exempt
@require_POST
@require_internal_secret
def storage_write(request):
    b = _body(request)
    content = base64.b64decode(b["content_b64"])
    _storage_for(b["activity_id"]).write(b["path"], content)
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
@require_internal_secret
def storage_exists(request):
    b = _body(request)
    exists = _storage_for(b["activity_id"]).exists(b["path"])
    return JsonResponse({"exists": exists})


@csrf_exempt
@require_POST
@require_internal_secret
def storage_list(request):
    b = _body(request)
    try:
        files, directories = _storage_for(b["activity_id"]).list(b["path"])
    except FileStorageError as e:
        return JsonResponse({"detail": str(e)}, status=404)
    return JsonResponse({"files": files, "directories": directories})


@csrf_exempt
@require_POST
@require_internal_secret
def storage_delete(request):
    b = _body(request)
    deleted = _storage_for(b["activity_id"]).delete(b["path"])
    return JsonResponse({"deleted": deleted})


# ------------------------------------------------------------------ #
# Usernames
# ------------------------------------------------------------------ #


@csrf_exempt
@require_POST
@require_internal_secret
def usernames(request):
    b = _body(request)
    User = get_user_model()
    rows = User.objects.filter(id__in=b["ids"]).all()
    return JsonResponse(
        {"usernames": [{"id": str(u.id), "username": u.username} for u in rows]}
    )
