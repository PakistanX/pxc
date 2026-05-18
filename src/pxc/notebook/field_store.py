"""SQLite-backed FieldStore implementation for the notebook application."""

import json
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import desc, event
from sqlmodel import Field, SQLModel, UniqueConstraint, col, select

from pxc.lib.field_store import FieldStore
from pxc.lib.fields import FieldType
from pxc.notebook import db


class FieldEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    course_id: str = Field(index=True)
    activity_name: str = Field(index=True)
    activity_id: str = Field(index=True)
    user_id: str = Field(index=True)
    key: str = Field(index=True)
    value: str  # JSON-encoded

    __table_args__ = (
        UniqueConstraint("course_id", "activity_name", "activity_id", "user_id", "key"),
    )


class FieldLogEntry(SQLModel, table=True):
    """A single entry in a log field. The auto-increment ``id`` is the entry id
    handed back to callers — strictly increasing but possibly sparse across logs.
    """

    id: int | None = Field(default=None, primary_key=True)
    course_id: str = Field(index=True)
    activity_name: str = Field(index=True)
    activity_id: str = Field(index=True)
    user_id: str = Field(index=True)
    key: str = Field(index=True)
    value: str  # JSON-encoded


def _key_filter(
    stmt: Any,
    model: type[FieldEntry] | type[FieldLogEntry],
    course_id: str,
    activity_name: str,
    activity_id: str,
    user_id: str,
    key: str,
) -> Any:
    """Apply the 5-column key filter to a statement."""
    return (
        stmt.where(col(model.course_id) == course_id)
        .where(col(model.activity_name) == activity_name)
        .where(col(model.activity_id) == activity_id)
        .where(col(model.user_id) == user_id)
        .where(col(model.key) == key)
    )


class SQLiteFieldStore(FieldStore):
    """FieldStore backed by SQLite via SQLModel."""

    def get(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> FieldType | None:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldEntry),
                FieldEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            )
            entry = session.exec(stmt).first()
            if entry is None:
                return None
            result: FieldType = json.loads(entry.value)
            return result

    def set(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> None:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldEntry),
                FieldEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            )
            entry = session.exec(stmt).first()
            encoded = json.dumps(value)
            if entry is None:
                entry = FieldEntry(
                    course_id=course_id,
                    activity_name=activity_name,
                    activity_id=activity_id,
                    user_id=user_id,
                    key=key,
                    value=encoded,
                )
            else:
                entry.value = encoded
            session.add(entry)
            session.commit()

    def delete(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> bool:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldEntry),
                FieldEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            )
            entry = session.exec(stmt).first()
            if entry is None:
                return False
            session.delete(entry)
            session.commit()
            return True

    def keys(self) -> list[str]:
        with db.session_scope() as session:
            entries = session.exec(select(FieldEntry.key)).all()
            return list(entries)

    def log_get(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> FieldType | None:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldLogEntry),
                FieldLogEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            ).where(col(FieldLogEntry.id) == entry_id)
            entry = session.exec(stmt).first()
            if entry is None:
                return None
            result: FieldType = json.loads(entry.value)
            return result

    def log_get_after(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        after_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldLogEntry),
                FieldLogEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            )
            if after_id is not None:
                stmt = stmt.where(col(FieldLogEntry.id) > after_id)
            stmt = stmt.order_by(col(FieldLogEntry.id)).limit(count)
            entries = session.exec(stmt).all()
            return [{"id": e.id, "value": json.loads(e.value)} for e in entries]

    def log_get_before(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int | None,
        count: int,
    ) -> list[dict[str, Any]]:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldLogEntry),
                FieldLogEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            )
            if before_id is not None:
                stmt = stmt.where(col(FieldLogEntry.id) < before_id)
            stmt = stmt.order_by(desc(col(FieldLogEntry.id))).limit(count)
            entries = session.exec(stmt).all()
            return [{"id": e.id, "value": json.loads(e.value)} for e in entries]

    def log_append(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        value: FieldType,
    ) -> int:
        with db.session_scope() as session:
            log_entry = FieldLogEntry(
                course_id=course_id,
                activity_name=activity_name,
                activity_id=activity_id,
                user_id=user_id,
                key=key,
                value=json.dumps(value),
            )
            session.add(log_entry)
            session.commit()
            session.refresh(log_entry)
            assert log_entry.id is not None
            return log_entry.id

    def log_delete(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        entry_id: int,
    ) -> bool:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldLogEntry),
                FieldLogEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            ).where(col(FieldLogEntry.id) == entry_id)
            entry = session.exec(stmt).first()
            if entry is None:
                return False
            session.delete(entry)
            session.commit()
            return True

    def log_delete_before(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
        before_id: int,
    ) -> int:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldLogEntry),
                FieldLogEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            ).where(col(FieldLogEntry.id) < before_id)
            entries = session.exec(stmt).all()
            count = len(entries)
            for entry in entries:
                session.delete(entry)
            if count > 0:
                session.commit()
            return count

    def log_clear(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        course_id: str,
        activity_name: str,
        activity_id: str,
        user_id: str,
        key: str,
    ) -> int:
        with db.session_scope() as session:
            stmt = _key_filter(
                select(FieldLogEntry),
                FieldLogEntry,
                course_id,
                activity_name,
                activity_id,
                user_id,
                key,
            )
            entries = session.exec(stmt).all()
            count = len(entries)
            for entry in entries:
                session.delete(entry)
            if count > 0:
                session.commit()
            return count


def delete_fields_by(
    activity_id: str | None = None,
    activity_name: str | None = None,
    course_id: str | None = None,
) -> None:
    """Delete all field data for a given course/activity type/id."""
    with db.session_scope() as session:
        for model in (FieldEntry, FieldLogEntry):
            select_filter = select(model)
            if course_id:
                select_filter = select_filter.where(col(model.course_id) == course_id)
            if activity_name:
                select_filter = select_filter.where(
                    col(model.activity_name) == activity_name
                )
            if activity_id:
                select_filter = select_filter.where(
                    col(model.activity_id) == activity_id
                )
            entries = session.exec(select_filter).all()
            for entry in entries:
                session.delete(entry)
        session.commit()


# ---------------------------------------------------------------------------
# Automatic field cleanup when activities are deleted via the ORM
# ---------------------------------------------------------------------------
# pylint: disable=wrong-import-position
from pxc.notebook.models import CourseActivity, PageActivity


def _on_activity_delete(_mapper: Any, connection: Any, target: Any) -> None:
    """Remove field store entries when an activity row is deleted."""
    for model in (FieldEntry, FieldLogEntry):
        connection.execute(sa_delete(model).where(col(model.activity_id) == target.id))


event.listen(PageActivity, "after_delete", _on_activity_delete)
event.listen(CourseActivity, "after_delete", _on_activity_delete)
