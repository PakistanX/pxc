"""Tests for DjangoFieldStore."""

from typing import Any

import pytest

try:
    import django
    from django.conf import settings

    if not settings.configured:
        settings.configure(
            DATABASES={
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": ":memory:",
                }
            },
            INSTALLED_APPS=["pxc.xblock"],
            DEFAULT_AUTO_FIELD="django.db.models.AutoField",
        )
        django.setup()

    from django.test.utils import setup_test_environment

    setup_test_environment()

    from django.db import connection

    with connection.schema_editor() as schema_editor:
        from pxc.xblock.models import (
            FieldEntry,
            FieldLogEntry,
            PendingEvent,
        )

        for model in (FieldEntry, FieldLogEntry, PendingEvent):
            try:
                schema_editor.create_model(model)
            except Exception:  # pylint: disable=broad-exception-caught
                pass  # table may already exist

    _DJANGO_AVAILABLE = True
except ImportError:
    _DJANGO_AVAILABLE = False


pytestmark = pytest.mark.skipif(not _DJANGO_AVAILABLE, reason="Django not available")


@pytest.fixture(autouse=True)
def clean_db() -> None:
    if not _DJANGO_AVAILABLE:
        return
    from pxc.xblock.models import FieldEntry, FieldLogEntry, PendingEvent

    FieldEntry.objects.all().delete()
    FieldLogEntry.objects.all().delete()
    PendingEvent.objects.all().delete()


def make_store() -> Any:
    from pxc.xblock.field_store import (
        DjangoFieldStore,
    )  # pylint: disable=import-outside-toplevel

    return DjangoFieldStore()


def test_set_get() -> None:
    store = make_store()
    store.set("c1", "mcq", "a1", "u1", "answer", 42)
    assert store.get("c1", "mcq", "a1", "u1", "answer") == 42


def test_get_missing_returns_none() -> None:
    store = make_store()
    assert store.get("c1", "mcq", "a1", "u1", "nope") is None


def test_set_overwrite() -> None:
    store = make_store()
    store.set("c1", "mcq", "a1", "u1", "x", "old")
    store.set("c1", "mcq", "a1", "u1", "x", "new")
    assert store.get("c1", "mcq", "a1", "u1", "x") == "new"


def test_delete() -> None:
    store = make_store()
    store.set("c1", "mcq", "a1", "u1", "x", 1)
    assert store.delete("c1", "mcq", "a1", "u1", "x") is True
    assert store.get("c1", "mcq", "a1", "u1", "x") is None
    assert store.delete("c1", "mcq", "a1", "u1", "x") is False


def test_log_append_returns_strictly_increasing_ids() -> None:
    store = make_store()
    id0 = store.log_append("c1", "quiz", "a1", "u1", "attempts", {"score": 5})
    id1 = store.log_append("c1", "quiz", "a1", "u1", "attempts", {"score": 8})
    assert id1 > id0
    assert store.log_get("c1", "quiz", "a1", "u1", "attempts", id0) == {"score": 5}
    assert store.log_get("c1", "quiz", "a1", "u1", "attempts", id1) == {"score": 8}
    assert store.log_get("c1", "quiz", "a1", "u1", "attempts", id1 + 999) is None


def test_log_get_after_from_start() -> None:
    store = make_store()
    ids = [store.log_append("c1", "quiz", "a1", "u1", "log", i) for i in range(5)]
    result = store.log_get_after("c1", "quiz", "a1", "u1", "log", None, 10)
    assert [r["id"] for r in result] == ids
    assert [r["value"] for r in result] == [0, 1, 2, 3, 4]


def test_log_get_after_with_cursor_and_count() -> None:
    store = make_store()
    ids = [store.log_append("c1", "quiz", "a1", "u1", "log", i) for i in range(5)]
    result = store.log_get_after("c1", "quiz", "a1", "u1", "log", ids[1], 2)
    assert [r["id"] for r in result] == [ids[2], ids[3]]
    assert [r["value"] for r in result] == [2, 3]


def test_log_get_before_from_end() -> None:
    store = make_store()
    ids = [store.log_append("c1", "quiz", "a1", "u1", "log", i) for i in range(5)]
    result = store.log_get_before("c1", "quiz", "a1", "u1", "log", None, 2)
    assert [r["id"] for r in result] == [ids[4], ids[3]]
    assert [r["value"] for r in result] == [4, 3]


def test_log_get_before_with_cursor() -> None:
    store = make_store()
    ids = [store.log_append("c1", "quiz", "a1", "u1", "log", i) for i in range(5)]
    result = store.log_get_before("c1", "quiz", "a1", "u1", "log", ids[3], 10)
    assert [r["id"] for r in result] == [ids[2], ids[1], ids[0]]


def test_log_delete() -> None:
    store = make_store()
    id_a = store.log_append("c1", "quiz", "a1", "u1", "log", "a")
    id_b = store.log_append("c1", "quiz", "a1", "u1", "log", "b")
    assert store.log_delete("c1", "quiz", "a1", "u1", "log", id_a) is True
    assert store.log_get("c1", "quiz", "a1", "u1", "log", id_a) is None
    assert store.log_get("c1", "quiz", "a1", "u1", "log", id_b) == "b"


def test_log_delete_before() -> None:
    store = make_store()
    ids = [store.log_append("c1", "quiz", "a1", "u1", "log", i) for i in range(5)]
    count = store.log_delete_before("c1", "quiz", "a1", "u1", "log", ids[3])
    assert count == 3
    for gone in ids[:3]:
        assert store.log_get("c1", "quiz", "a1", "u1", "log", gone) is None
    assert store.log_get("c1", "quiz", "a1", "u1", "log", ids[3]) == 3
    assert store.log_get("c1", "quiz", "a1", "u1", "log", ids[4]) == 4


def test_log_clear() -> None:
    store = make_store()
    ids = [store.log_append("c1", "quiz", "a1", "u1", "log", i) for i in range(3)]
    count = store.log_clear("c1", "quiz", "a1", "u1", "log")
    assert count == 3
    for gone in ids:
        assert store.log_get("c1", "quiz", "a1", "u1", "log", gone) is None
    assert store.log_clear("c1", "quiz", "a1", "u1", "log") == 0


def test_log_clear_scoped_per_key() -> None:
    store = make_store()
    store.log_append("c1", "quiz", "a1", "u1", "log_a", 1)
    store.log_append("c1", "quiz", "a1", "u1", "log_b", 2)
    assert store.log_clear("c1", "quiz", "a1", "u1", "log_a") == 1
    result = store.log_get_after("c1", "quiz", "a1", "u1", "log_b", None, 10)
    assert [r["value"] for r in result] == [2]


def test_pending_event_retention_sweep() -> None:
    """The query the action handler uses to prune old PendingEvent rows."""
    from datetime import timedelta  # pylint: disable=import-outside-toplevel

    from django.utils import (  # pylint: disable=import-outside-toplevel
        timezone,
    )

    from pxc.xblock.models import (  # pylint: disable=import-outside-toplevel
        PendingEvent,
    )

    old = PendingEvent.objects.create(
        course_id="c",
        activity_id="a",
        event_name="x",
        event_value="{}",
        event_context="{}",
        event_permission="play",
    )
    # auto_now_add can't be set at create time; backdate with update().
    PendingEvent.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(hours=25)
    )
    fresh = PendingEvent.objects.create(
        course_id="c",
        activity_id="a",
        event_name="y",
        event_value="{}",
        event_context="{}",
        event_permission="play",
    )

    cutoff = timezone.now() - timedelta(hours=24)
    deleted, _ = PendingEvent.objects.filter(created_at__lt=cutoff).delete()

    assert deleted == 1
    assert not PendingEvent.objects.filter(pk=old.pk).exists()
    assert PendingEvent.objects.filter(pk=fresh.pk).exists()
