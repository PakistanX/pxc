"""FieldStore implementation that proxies every operation back to pxc-xblock.

Field rows live in the LMS/CMS database (Django ORM, `FieldEntry` /
`FieldLogEntry`) which this process has no direct access to — so every read
and write is a synchronous HTTP callback to the xblock internal API.
"""

from typing import Any

from pxc.lib.field_store import FieldStore
from pxc.lib.fields import FieldType
from pxc.libserver import client


class HttpFieldStore(FieldStore):
    """FieldStore backed by HTTP callbacks to pxc.xblock's internal API."""

    def get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> FieldType | None:
        result = client.post(
            "/fields/get",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
            },
        )
        value: FieldType | None = result["value"]
        return value

    def set(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> None:
        client.post(
            "/fields/set",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
                "value": value,
            },
        )

    def delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> bool:
        result = client.post(
            "/fields/delete",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
            },
        )
        return bool(result["deleted"])

    def keys(self) -> list[str]:
        # Unused by ActivityRuntime (dead in the reference implementation
        # too — see pxc.lib.field_store.FieldStore.keys) so no internal
        # endpoint is wired up for it.
        raise NotImplementedError("HttpFieldStore.keys() is not supported")

    def log_get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> FieldType | None:
        result = client.post(
            "/fields/log/get",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
                "entry_id": entry_id,
            },
        )
        value: FieldType | None = result["value"]
        return value

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
        result = client.post(
            "/fields/log/get_after",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
                "after_id": after_id,
                "count": count,
            },
        )
        entries: list[dict[str, Any]] = result["entries"]
        return entries

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
        result = client.post(
            "/fields/log/get_before",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
                "before_id": before_id,
                "count": count,
            },
        )
        entries: list[dict[str, Any]] = result["entries"]
        return entries

    def log_append(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> int:
        result = client.post(
            "/fields/log/append",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
                "value": value,
            },
        )
        return int(result["id"])

    def log_delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> bool:
        result = client.post(
            "/fields/log/delete",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
                "entry_id": entry_id,
            },
        )
        return bool(result["deleted"])

    def log_delete_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int,
    ) -> int:
        result = client.post(
            "/fields/log/delete_before",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
                "before_id": before_id,
            },
        )
        return int(result["deleted"])

    def log_clear(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> int:
        result = client.post(
            "/fields/log/clear",
            {
                "course_id": course_id,
                "activity_name": activity_name,
                "activity_id": activity_id,
                "user_id": user_id,
                "key": key,
            },
        )
        return int(result["deleted"])
