"""Django ORM-backed field store for PXC XBlock.

Called from internal_api.py (HTTP callbacks from the standalone lib-server)
rather than injected into an in-process `ActivityRuntime` — pxc-xblock no
longer depends on pxc-lib, so this is a plain class, not an ABC subclass.

Targets Python 3.5 / Django 2.2 (Juniper-era Open edX): no f-strings, no PEP
526 variable annotations, no bare generic subscripting (``dict[str, int]``),
no ``X | Y`` unions, no ``from __future__ import annotations`` (that feature
itself needs Python 3.7+). ``FieldEntry.value`` / ``FieldLogEntry.value`` are
``TextField``s (see models.py) — this module owns the json.dumps/loads at
the boundary since Django 2.2 has no cross-database ``JSONField``.
"""

import json
from typing import Any, Dict, List, Optional, Union

from pxc.xblock.models import FieldEntry, FieldLogEntry

FieldType = Union[int, float, str, bool, List[Any], Dict[str, Any]]


def _scope(course_id, activity_name, activity_id, user_id, key):
    # type: (str, str, str, str, str) -> Dict[str, str]
    """Build the 5-tuple filter shared by every (log_)? operation."""
    return {
        "course_id": course_id,
        "activity_name": activity_name,
        "activity_id": activity_id,
        "user_id": user_id,
        "key": key,
    }


class DjangoFieldStore(object):
    """FieldStore backed by the Django ORM (pxc_xblock Django app tables)."""

    def get(self, course_id, activity_name, activity_id, user_id, key):
        # type: (str, str, str, str, str) -> Optional[FieldType]
        entry = FieldEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).first()
        if entry is None:
            return None
        return json.loads(entry.value)

    def set(self, course_id, activity_name, activity_id, user_id, key, value):
        # type: (str, str, str, str, str, FieldType) -> None
        FieldEntry.objects.update_or_create(
            defaults={"value": json.dumps(value)},
            **_scope(course_id, activity_name, activity_id, user_id, key)
        )

    def delete(self, course_id, activity_name, activity_id, user_id, key):
        # type: (str, str, str, str, str) -> bool
        deleted, _ = FieldEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).delete()
        return int(deleted) > 0

    def keys(self):
        # type: () -> List[str]
        return list(FieldEntry.objects.values_list("key", flat=True))

    def reset_learner(self, course_id, activity_name, activity_id, user_id):
        # type: (str, str, str, str) -> Dict[str, int]
        """Delete every field/log row this activity instance wrote for one user.

        Used by the Studio "reset a learner's attempt" action. Scoped to a
        real ``user_id`` only, so course/activity/global-scoped rows (stored
        with ``user_id=""``, e.g. a shared course-scope API key) are never
        touched — those don't belong to any one learner.
        """
        if not user_id:
            raise ValueError("reset_learner requires a non-empty user_id")
        fields_deleted, _ = FieldEntry.objects.filter(
            course_id=course_id,
            activity_name=activity_name,
            activity_id=activity_id,
            user_id=user_id,
        ).delete()
        log_entries_deleted, _ = FieldLogEntry.objects.filter(
            course_id=course_id,
            activity_name=activity_name,
            activity_id=activity_id,
            user_id=user_id,
        ).delete()
        return {
            "fields_deleted": int(fields_deleted),
            "log_entries_deleted": int(log_entries_deleted),
        }

    def log_get(self, course_id, activity_name, activity_id, user_id, key, entry_id):
        # type: (str, str, str, str, str, int) -> Optional[FieldType]
        entry = FieldLogEntry.objects.filter(
            id=entry_id,
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).first()
        if entry is None:
            return None
        return json.loads(entry.value)

    def log_get_after(
        self, course_id, activity_name, activity_id, user_id, key, after_id, count
    ):
        # type: (str, str, str, str, str, Optional[int], int) -> List[Dict[str, Any]]
        qs = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        )
        if after_id is not None:
            qs = qs.filter(id__gt=after_id)
        entries = qs.order_by("id")[:count]
        return [{"id": e.id, "value": json.loads(e.value)} for e in entries]

    def log_get_before(
        self, course_id, activity_name, activity_id, user_id, key, before_id, count
    ):
        # type: (str, str, str, str, str, Optional[int], int) -> List[Dict[str, Any]]
        qs = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        )
        if before_id is not None:
            qs = qs.filter(id__lt=before_id)
        entries = qs.order_by("-id")[:count]
        return [{"id": e.id, "value": json.loads(e.value)} for e in entries]

    def log_append(self, course_id, activity_name, activity_id, user_id, key, value):
        # type: (str, str, str, str, str, FieldType) -> int
        entry = FieldLogEntry.objects.create(
            value=json.dumps(value),
            **_scope(course_id, activity_name, activity_id, user_id, key)
        )
        assert entry.id is not None
        return int(entry.id)

    def log_delete(
        self, course_id, activity_name, activity_id, user_id, key, entry_id
    ):
        # type: (str, str, str, str, str, int) -> bool
        deleted, _ = FieldLogEntry.objects.filter(
            id=entry_id,
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).delete()
        return int(deleted) > 0

    def log_delete_before(
        self, course_id, activity_name, activity_id, user_id, key, before_id
    ):
        # type: (str, str, str, str, str, int) -> int
        deleted, _ = FieldLogEntry.objects.filter(
            id__lt=before_id,
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).delete()
        return int(deleted)

    def log_clear(self, course_id, activity_name, activity_id, user_id, key):
        # type: (str, str, str, str, str) -> int
        deleted, _ = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).delete()
        return int(deleted)
