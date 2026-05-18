import json
from pathlib import Path

import pytest

from pxc.lib.runtime import ActivityRuntime, SandboxContext
from pxc.lib.fields import FieldValidationError
from pxc.lib.file_storage import MemoryFileStorage
from pxc.lib.permission import Permission
from .utils import (
    create_manifest,
    make_field_store,
    setup_activity_dir,
    make_activity_runtime,
)


def make_ctx(tmp_path: Path) -> ActivityRuntime:
    manifest = create_manifest(
        fields={
            "messages": {
                "type": "log",
                "items": {
                    "type": "object",
                    "properties": {
                        "user": {"type": "string"},
                        "text": {"type": "string"},
                    },
                },
                "scope": "activity",
            }
        }
    )
    activity_dir = setup_activity_dir(tmp_path, manifest)
    return ActivityRuntime(
        activity_dir,
        make_field_store(),
        MemoryFileStorage(),
        "activityid",
        "courseid",
        "userid",
        Permission.play,
    )


class TestLogFieldFunctions:
    """Tests for log_* host functions."""

    def test_log_append_returns_strictly_increasing_ids(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        id0 = ctx.log_append("messages", json.dumps({"user": "alice", "text": "hi"}))
        id1 = ctx.log_append("messages", json.dumps({"user": "bob", "text": "hello"}))
        assert id1 > id0

    def test_log_get_retrieves_by_id(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        id0 = ctx.log_append("messages", json.dumps({"user": "alice", "text": "hi"}))
        id1 = ctx.log_append("messages", json.dumps({"user": "bob", "text": "hello"}))
        assert json.loads(ctx.log_get("messages", id0)) == {
            "user": "alice",
            "text": "hi",
        }
        assert json.loads(ctx.log_get("messages", id1)) == {
            "user": "bob",
            "text": "hello",
        }

    def test_log_get_missing_returns_none(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        assert json.loads(ctx.log_get("messages", 99)) is None

    def test_log_get_after_from_start(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        ids = [
            ctx.log_append("messages", json.dumps({"user": "a", "text": "1"})),
            ctx.log_append("messages", json.dumps({"user": "b", "text": "2"})),
            ctx.log_append("messages", json.dumps({"user": "c", "text": "3"})),
        ]
        result = json.loads(ctx.log_get_after("messages", None, 10))
        assert [r["id"] for r in result] == ids
        assert result[0]["value"] == {"user": "a", "text": "1"}
        assert result[2]["value"] == {"user": "c", "text": "3"}

    def test_log_get_after_with_cursor(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        id0 = ctx.log_append("messages", json.dumps({"user": "a", "text": "1"}))
        id1 = ctx.log_append("messages", json.dumps({"user": "b", "text": "2"}))
        id2 = ctx.log_append("messages", json.dumps({"user": "c", "text": "3"}))
        result = json.loads(ctx.log_get_after("messages", id0, 10))
        assert [r["id"] for r in result] == [id1, id2]

    def test_log_get_after_respects_count(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        for i in range(5):
            ctx.log_append("messages", json.dumps({"user": "u", "text": str(i)}))
        result = json.loads(ctx.log_get_after("messages", None, 2))
        assert len(result) == 2

    def test_log_get_before_from_end(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        ids = [
            ctx.log_append("messages", json.dumps({"user": "a", "text": "1"})),
            ctx.log_append("messages", json.dumps({"user": "b", "text": "2"})),
            ctx.log_append("messages", json.dumps({"user": "c", "text": "3"})),
        ]
        result = json.loads(ctx.log_get_before("messages", None, 2))
        assert [r["id"] for r in result] == [ids[2], ids[1]]
        assert result[0]["value"] == {"user": "c", "text": "3"}

    def test_log_get_before_with_cursor(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        id0 = ctx.log_append("messages", json.dumps({"user": "a", "text": "1"}))
        id1 = ctx.log_append("messages", json.dumps({"user": "b", "text": "2"}))
        ctx.log_append("messages", json.dumps({"user": "c", "text": "3"}))
        result = json.loads(ctx.log_get_before("messages", id1, 10))
        assert [r["id"] for r in result] == [id0]

    def test_log_delete(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        id0 = ctx.log_append("messages", json.dumps({"user": "a", "text": "1"}))
        assert ctx.log_delete("messages", id0) is True
        assert json.loads(ctx.log_get("messages", id0)) is None

    def test_log_delete_missing(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        assert ctx.log_delete("messages", 99) is False

    def test_log_delete_before(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        id0 = ctx.log_append("messages", json.dumps({"user": "a", "text": "1"}))
        id1 = ctx.log_append("messages", json.dumps({"user": "b", "text": "2"}))
        id2 = ctx.log_append("messages", json.dumps({"user": "c", "text": "3"}))
        count = ctx.log_delete_before("messages", id2)
        assert count == 2
        assert json.loads(ctx.log_get("messages", id0)) is None
        assert json.loads(ctx.log_get("messages", id1)) is None
        assert json.loads(ctx.log_get("messages", id2)) == {"user": "c", "text": "3"}

    def test_log_clear(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        ids = [
            ctx.log_append("messages", json.dumps({"user": "a", "text": "1"})),
            ctx.log_append("messages", json.dumps({"user": "b", "text": "2"})),
        ]
        count = ctx.log_clear("messages")
        assert count == 2
        for entry_id in ids:
            assert json.loads(ctx.log_get("messages", entry_id)) is None
        assert ctx.log_clear("messages") == 0

    def test_get_field_raises_on_log(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        with pytest.raises(FieldValidationError, match="type 'log'"):
            ctx.get_field("messages")

    def test_set_field_raises_on_log(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        with pytest.raises(FieldValidationError, match="type 'log'"):
            ctx.set_field("messages", "[]")

    def test_scope_override(self, tmp_path: Path) -> None:
        manifest = create_manifest(
            fields={
                "messages": {
                    "type": "log",
                    "items": {"type": "string"},
                    "scope": "user,activity",
                }
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.user_id = "alice"

        alice_id = ctx.log_append("messages", json.dumps("alice msg"))
        bob_id = ctx.log_append(
            "messages",
            json.dumps("bob msg"),
            SandboxContext({"activity-id": None, "course-id": None, "user-id": "bob"}),
        )

        assert json.loads(ctx.log_get("messages", alice_id)) == "alice msg"
        assert (
            json.loads(
                ctx.log_get(
                    "messages",
                    bob_id,
                    SandboxContext(
                        {"activity-id": None, "course-id": None, "user-id": "bob"}
                    ),
                )
            )
            == "bob msg"
        )

    def test_item_validation_rejects_wrong_type(self, tmp_path: Path) -> None:
        ctx = make_ctx(tmp_path)
        with pytest.raises(FieldValidationError, match="item failed validation"):
            ctx.log_append("messages", json.dumps("not an object"))

    def test_get_all_fields_skips_log(self, tmp_path: Path) -> None:
        manifest = create_manifest(
            fields={
                "messages": {
                    "type": "log",
                    "items": {"type": "string"},
                    "scope": "activity",
                },
                "count": {"type": "integer", "scope": "activity"},
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        result = ctx.get_all_fields()
        assert "count" in result
        assert "messages" not in result
