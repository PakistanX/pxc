"""FieldStore — abstract base class for field persistence."""

from abc import ABC, abstractmethod
from typing import Any

from pxc.lib.fields import FieldType


class FieldStore(ABC):
    """Abstract base class for storing scalar and log field data."""

    # Scalar fields
    @abstractmethod
    def get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> FieldType | None: ...

    @abstractmethod
    def set(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> None: ...

    @abstractmethod
    def delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> bool: ...

    @abstractmethod
    def keys(self) -> list[str]: ...

    # Log fields
    @abstractmethod
    def log_get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> FieldType | None: ...

    @abstractmethod
    def log_get_after(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        after_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def log_get_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]: ...

    @abstractmethod
    def log_append(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> int: ...

    @abstractmethod
    def log_delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> bool: ...

    @abstractmethod
    def log_delete_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int,
    ) -> int: ...

    @abstractmethod
    def log_clear(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> int: ...


class MemoryKVStore(FieldStore):
    """Non-persistent key-value store"""

    def __init__(self) -> None:
        self._data: dict[str, FieldType] = {}

    @staticmethod
    def _composite_key(
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> str:
        return f"pxc.{activity_name}.{course_id}.{activity_id}.{user_id}.{key}"

    def get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> FieldType | None:
        return self._data.get(
            self._composite_key(course_id, activity_name, activity_id, user_id, key)
        )

    def set(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> None:
        self._data[
            self._composite_key(course_id, activity_name, activity_id, user_id, key)
        ] = value

    def delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> bool:
        ck = self._composite_key(course_id, activity_name, activity_id, user_id, key)
        if ck in self._data:
            del self._data[ck]
            return True
        return False

    def keys(self) -> list[str]:
        return list(self._data.keys())

    # Log field methods

    def _log_key(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> str:
        return self._composite_key(
            course_id, activity_name, activity_id, user_id, f"__log__.{key}"
        )

    def _log_data(self, log_key: str) -> dict[str, Any]:
        stored = self._data.get(log_key)
        if stored is None:
            return {"next_id": 0, "entries": {}}
        assert isinstance(stored, dict)
        return stored

    def log_get(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> FieldType | None:
        data = self._log_data(
            self._log_key(course_id, activity_name, activity_id, user_id, key)
        )
        value: FieldType | None = data["entries"].get(str(entry_id))
        return value

    def _sorted_ids(self, data: dict[str, Any]) -> list[int]:
        return sorted(int(k) for k in data["entries"].keys())

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
        data = self._log_data(
            self._log_key(course_id, activity_name, activity_id, user_id, key)
        )
        ids = self._sorted_ids(data)
        if after_id is not None:
            ids = [i for i in ids if i > after_id]
        return [{"id": i, "value": data["entries"][str(i)]} for i in ids[:count]]

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
        data = self._log_data(
            self._log_key(course_id, activity_name, activity_id, user_id, key)
        )
        ids = self._sorted_ids(data)
        if before_id is not None:
            ids = [i for i in ids if i < before_id]
        return [
            {"id": i, "value": data["entries"][str(i)]} for i in reversed(ids[-count:])
        ]

    def log_append(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> int:
        lk = self._log_key(course_id, activity_name, activity_id, user_id, key)
        data = self._log_data(lk)
        entry_id: int = data["next_id"]
        data["entries"][str(entry_id)] = value
        data["next_id"] = entry_id + 1
        self._data[lk] = data
        return entry_id

    def log_delete(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> bool:
        lk = self._log_key(course_id, activity_name, activity_id, user_id, key)
        data = self._log_data(lk)
        k = str(entry_id)
        if k not in data["entries"]:
            return False
        del data["entries"][k]
        self._data[lk] = data
        return True

    def log_delete_before(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int,
    ) -> int:
        lk = self._log_key(course_id, activity_name, activity_id, user_id, key)
        data = self._log_data(lk)
        victims = [i for i in self._sorted_ids(data) if i < before_id]
        for i in victims:
            del data["entries"][str(i)]
        if victims:
            self._data[lk] = data
        return len(victims)

    def log_clear(
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> int:
        lk = self._log_key(course_id, activity_name, activity_id, user_id, key)
        data = self._log_data(lk)
        count = len(data["entries"])
        if count == 0:
            return 0
        data["entries"] = {}
        self._data[lk] = data
        return count
