"""Django ORM-backed FieldStore for PXC XBlock."""

from typing import Any

from pxc.lib.field_store import FieldStore
from pxc.lib.fields import FieldType
from pxc.xblock.models import FieldEntry, FieldLogEntry


def _scope(
    course_id: str,
    activity_name: str,
    activity_id: str,
    user_id: str,
    key: str,
) -> dict[str, str]:
    """Build the 5-tuple filter shared by every (log_)? operation."""
    return {
        "course_id": course_id,
        "activity_name": activity_name,
        "activity_id": activity_id,
        "user_id": user_id,
        "key": key,
    }


class DjangoFieldStore(FieldStore):
    """FieldStore backed by the Django ORM (pxc_xblock Django app tables)."""

    def get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> FieldType | None:
        entry = FieldEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).first()
        if entry is None:
            return None
        result: FieldType = entry.value
        return result

    def set(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> None:
        FieldEntry.objects.update_or_create(
            **_scope(course_id, activity_name, activity_id, user_id, key),
            defaults={"value": value},
        )

    def delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> bool:
        deleted, _ = FieldEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).delete()
        return int(deleted) > 0

    def keys(self) -> list[str]:
        return list(FieldEntry.objects.values_list("key", flat=True))

    def log_get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> FieldType | None:
        entry = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key),
            id=entry_id,
        ).first()
        if entry is None:
            return None
        result: FieldType = entry.value
        return result

    def log_get_after(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        after_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]:
        qs = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        )
        if after_id is not None:
            qs = qs.filter(id__gt=after_id)
        entries = qs.order_by("id")[:count]
        return [{"id": e.id, "value": e.value} for e in entries]

    def log_get_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]:
        qs = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        )
        if before_id is not None:
            qs = qs.filter(id__lt=before_id)
        entries = qs.order_by("-id")[:count]
        return [{"id": e.id, "value": e.value} for e in entries]

    def log_append(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> int:
        entry = FieldLogEntry.objects.create(
            **_scope(course_id, activity_name, activity_id, user_id, key),
            value=value,
        )
        assert entry.id is not None
        return int(entry.id)

    def log_delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> bool:
        deleted, _ = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key),
            id=entry_id,
        ).delete()
        return int(deleted) > 0

    def log_delete_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int,
    ) -> int:
        deleted, _ = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key),
            id__lt=before_id,
        ).delete()
        return int(deleted)

    def log_clear(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> int:
        deleted, _ = FieldLogEntry.objects.filter(
            **_scope(course_id, activity_name, activity_id, user_id, key)
        ).delete()
        return int(deleted)
