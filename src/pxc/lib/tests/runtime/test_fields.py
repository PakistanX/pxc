import json
from pathlib import Path

import pytest

from pxc.lib.fields import FieldValidationError
from pxc.lib.runtime import SandboxContext

from .utils import create_manifest, make_activity_runtime


class TestLoadField:
    """Tests for load_field method."""

    def test_returns_default_when_not_set(self, tmp_path: Path) -> None:
        """Should return default value when field not yet stored."""
        manifest = create_manifest(
            fields={
                "score": {
                    "type": "integer",
                    "scope": "user,activity",
                    "default": 0,
                }
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        result = ctx.load_field("a", "c", "alice", "score")

        assert result == 0

    def test_returns_type_default_when_no_explicit_default(
        self, tmp_path: Path
    ) -> None:
        """Should return type-specific default when no explicit default."""
        manifest = create_manifest(
            fields={
                "count": {"type": "integer", "scope": "user,activity"},
                "ratio": {"type": "number", "scope": "user,activity"},
                "name": {"type": "string", "scope": "user,activity"},
                "done": {"type": "boolean", "scope": "user,activity"},
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        assert ctx.load_field("a", "c", user, "count") == 0
        assert ctx.load_field("a", "c", user, "ratio") == 0.0
        assert ctx.load_field("a", "c", user, "name") == ""
        assert ctx.load_field("a", "c", user, "done") is False

    def test_returns_stored_value(self, tmp_path: Path) -> None:
        """Should return stored value when set."""
        manifest = create_manifest(
            fields={
                "score": {
                    "type": "integer",
                    "scope": "user,activity",
                    "default": 0,
                }
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        ctx.store_field("c", "a", user, "score", 42)
        result = ctx.load_field("a", "c", user, "score")

        assert result == 42

    def test_raises_for_undeclared_field(self, tmp_path: Path) -> None:
        """Should raise for field not declared in manifest."""
        manifest = create_manifest(
            fields={"score": {"type": "integer", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        with pytest.raises(FieldValidationError, match="not declared"):
            ctx.load_field("a", "c", "alice", "unknown")

    def test_fields_isolated_by_user(self, tmp_path: Path) -> None:
        """Should store separate values for different users."""
        manifest = create_manifest(
            fields={
                "score": {
                    "type": "integer",
                    "scope": "user,activity",
                    "default": 0,
                }
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        base_user = "alice"

        ctx.store_field("c", "a", f"{base_user}_1", "score", 10)
        ctx.store_field("c", "a", f"{base_user}_2", "score", 20)

        assert ctx.load_field("a", "c", f"{base_user}_1", "score") == 10
        assert ctx.load_field("a", "c", f"{base_user}_2", "score") == 20

    def test_shared_field_uses_empty_user_id(self, tmp_path: Path) -> None:
        """Should use empty string for shared (non-user) fields."""
        manifest = create_manifest(
            fields={
                "question": {
                    "type": "string",
                    "scope": "activity",
                    "default": "",
                }
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.store_field("c", "a", "", "question", "What is 2+2?")
        result = ctx.load_field("a", "c", "", "question")

        assert result == "What is 2+2?"


class TestStoreField:
    """Tests for store_field method."""

    def test_stores_integer(self, tmp_path: Path) -> None:
        """Should store and retrieve integer value."""
        manifest = create_manifest(
            fields={"count": {"type": "integer", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        ctx.store_field("c", "a", user, "count", 42)

        assert ctx.load_field("a", "c", user, "count") == 42

    def test_stores_float(self, tmp_path: Path) -> None:
        """Should store and retrieve float value."""
        manifest = create_manifest(
            fields={"ratio": {"type": "number", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        ctx.store_field("c", "a", user, "ratio", 3.14)

        assert ctx.load_field("a", "c", user, "ratio") == 3.14

    def test_stores_string(self, tmp_path: Path) -> None:
        """Should store and retrieve string value."""
        manifest = create_manifest(
            fields={"name": {"type": "string", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        ctx.store_field("c", "a", user, "name", "Alice")

        assert ctx.load_field("a", "c", user, "name") == "Alice"

    def test_stores_boolean(self, tmp_path: Path) -> None:
        """Should store and retrieve boolean value."""
        manifest = create_manifest(
            fields={"completed": {"type": "boolean", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        ctx.store_field("c", "a", user, "completed", True)

        assert ctx.load_field("a", "c", user, "completed") is True

    def test_stores_array(self, tmp_path: Path) -> None:
        """Should store and retrieve array value."""
        manifest = create_manifest(
            fields={
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "scope": "user,activity",
                }
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        ctx.store_field("c", "a", user, "tags", ["a", "b", "c"])

        assert ctx.load_field("a", "c", user, "tags") == ["a", "b", "c"]

    def test_raises_for_wrong_type(self, tmp_path: Path) -> None:
        """Should raise when value type doesn't match declaration."""
        manifest = create_manifest(
            fields={"count": {"type": "integer", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        with pytest.raises(FieldValidationError, match="failed validation"):
            ctx.store_field("c", "a", user, "count", "not an int")

    def test_raises_for_undeclared_field(self, tmp_path: Path) -> None:
        """Should raise for field not declared in manifest."""
        manifest = create_manifest(
            fields={"score": {"type": "integer", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        with pytest.raises(FieldValidationError, match="not declared"):
            ctx.store_field("c", "a", user, "unknown", 42)

    def test_overwrites_existing_value(self, tmp_path: Path) -> None:
        """Should overwrite previously stored value."""
        manifest = create_manifest(
            fields={"count": {"type": "integer", "scope": "user,activity"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        user = "alice"

        ctx.store_field("c", "a", user, "count", 10)
        ctx.store_field("c", "a", user, "count", 20)

        assert ctx.load_field("a", "c", user, "count") == 20


class TestGetAllFields:
    """Tests for get_all_fields method."""

    def test_returns_all_fields(self, tmp_path: Path) -> None:
        """Should return all declared fields."""
        manifest = create_manifest(
            fields={
                "public": {"type": "string", "scope": "activity"},
                "secret": {"type": "string", "scope": "activity"},
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        result = ctx.get_all_fields()
        assert "public" in result
        assert "secret" in result

    def test_includes_user_scoped_fields(self, tmp_path: Path) -> None:
        """Should include user-scoped fields loaded for the given user."""
        manifest = create_manifest(
            fields={
                "score": {
                    "type": "integer",
                    "scope": "user,activity",
                    "default": 0,
                },
                "question": {
                    "type": "string",
                    "scope": "activity",
                    "default": "",
                },
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.store_field(ctx.course_id, ctx.activity_id, ctx.user_id, "score", 42)
        ctx.store_field(ctx.course_id, ctx.activity_id, "", "question", "What is 2+2?")

        result = ctx.get_all_fields()
        assert result == {"score": 42, "question": "What is 2+2?"}

    def test_includes_course_scoped_fields(self, tmp_path: Path) -> None:
        """Should include course-scoped and user,course-scoped fields."""
        manifest = create_manifest(
            fields={
                "course_total": {
                    "type": "integer",
                    "scope": "course",
                    "default": 0,
                },
                "course_score": {
                    "type": "integer",
                    "scope": "user,course",
                    "default": 0,
                },
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.store_field(ctx.course_id, "", "", "course_total", 100)
        ctx.store_field(ctx.course_id, "", ctx.user_id, "course_score", 85)

        result = ctx.get_all_fields()
        assert result == {"course_total": 100, "course_score": 85}

    def test_includes_global_scoped_fields(self, tmp_path: Path) -> None:
        """Should include global-scoped and user,global-scoped fields."""
        manifest = create_manifest(
            fields={
                "global_setting": {
                    "type": "string",
                    "scope": "global",
                    "default": "",
                },
                "global_pref": {
                    "type": "string",
                    "scope": "user,global",
                    "default": "",
                },
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.store_field("", "", "", "global_setting", "on")
        ctx.store_field("", "", ctx.user_id, "global_pref", "dark")

        result = ctx.get_all_fields()
        assert result == {"global_setting": "on", "global_pref": "dark"}


class TestScopeAwareGetSetField:
    """Tests for scope-aware get_field/set_field host functions."""

    def test_activity_scope(self, tmp_path: Path) -> None:
        """Should get/set activity-scoped fields."""
        manifest = create_manifest(
            fields={"question": {"type": "string", "scope": "activity", "default": ""}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        assert json.loads(ctx.get_field("question")) == ""
        ctx.set_field("question", json.dumps("What is 2+2?"))
        assert json.loads(ctx.get_field("question")) == "What is 2+2?"

    def test_user_activity_scope(self, tmp_path: Path) -> None:
        """Should get/set user,activity-scoped fields."""
        manifest = create_manifest(
            fields={
                "score": {"type": "integer", "scope": "user,activity", "default": 0}
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.user_id = "alice"

        assert json.loads(ctx.get_field("score")) == 0
        ctx.set_field("score", json.dumps(42))
        assert json.loads(ctx.get_field("score")) == 42

    def test_course_scope(self, tmp_path: Path) -> None:
        """Should get/set course-scoped fields."""
        manifest = create_manifest(
            fields={"total": {"type": "integer", "scope": "course", "default": 0}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        assert json.loads(ctx.get_field("total")) == 0
        ctx.set_field("total", json.dumps(99))
        assert json.loads(ctx.get_field("total")) == 99

    def test_user_course_scope(self, tmp_path: Path) -> None:
        """Should get/set user,course-scoped fields."""
        manifest = create_manifest(
            fields={"grade": {"type": "integer", "scope": "user,course", "default": 0}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.user_id = "alice"

        assert json.loads(ctx.get_field("grade")) == 0
        ctx.set_field("grade", json.dumps(85))
        assert json.loads(ctx.get_field("grade")) == 85

    def test_global_scope(self, tmp_path: Path) -> None:
        """Should get/set global-scoped fields."""
        manifest = create_manifest(
            fields={"setting": {"type": "string", "scope": "global", "default": ""}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        assert json.loads(ctx.get_field("setting")) == ""
        ctx.set_field("setting", json.dumps("dark"))
        assert json.loads(ctx.get_field("setting")) == "dark"

    def test_user_global_scope(self, tmp_path: Path) -> None:
        """Should get/set user,global-scoped fields."""
        manifest = create_manifest(
            fields={"pref": {"type": "string", "scope": "user,global", "default": ""}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.user_id = "alice"

        assert json.loads(ctx.get_field("pref")) == ""
        ctx.set_field("pref", json.dumps("en"))
        assert json.loads(ctx.get_field("pref")) == "en"

    def test_different_scopes_isolated(self, tmp_path: Path) -> None:
        """Fields with different scopes should not collide."""
        manifest = create_manifest(
            fields={
                "count_activity": {
                    "type": "integer",
                    "scope": "activity",
                    "default": 0,
                },
                "count_course": {"type": "integer", "scope": "course", "default": 0},
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.set_field("count_activity", json.dumps(10))
        ctx.set_field("count_course", json.dumps(20))

        assert json.loads(ctx.get_field("count_activity")) == 10
        assert json.loads(ctx.get_field("count_course")) == 20


class TestFieldScopeOverrides:
    """Tests for get_field/set_field with scope overrides."""

    def test_get_field_with_user_override(self, tmp_path: Path) -> None:
        """Should read another user's user,activity field via scope override."""
        manifest = create_manifest(
            fields={
                "score": {"type": "integer", "scope": "user,activity", "default": 0}
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.user_id = "alice"

        ctx.set_field(
            "score",
            json.dumps(42),
            SandboxContext({"activity-id": None, "course-id": None, "user-id": "bob"}),
        )

        assert (
            json.loads(
                ctx.get_field(
                    "score",
                    SandboxContext(
                        {"activity-id": None, "course-id": None, "user-id": "bob"}
                    ),
                )
            )
            == 42
        )
        assert json.loads(ctx.get_field("score")) == 0

    def test_set_field_with_user_override(self, tmp_path: Path) -> None:
        """Should write another user's user,activity field via scope override."""
        manifest = create_manifest(
            fields={
                "score": {"type": "integer", "scope": "user,activity", "default": 0}
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.user_id = "alice"

        ctx.set_field(
            "score",
            json.dumps(99),
            SandboxContext({"activity-id": None, "course-id": None, "user-id": "bob"}),
        )

        assert (
            json.loads(
                ctx.get_field(
                    "score",
                    SandboxContext(
                        {"activity-id": None, "course-id": None, "user-id": "bob"}
                    ),
                )
            )
            == 99
        )
        assert json.loads(ctx.get_field("score")) == 0

    def test_scope_override_invalid_key_raises(self, tmp_path: Path) -> None:
        """Should raise FieldValidationError for invalid override key on course-scoped field."""
        manifest = create_manifest(
            fields={"total": {"type": "integer", "scope": "course", "default": 0}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        with pytest.raises(FieldValidationError, match="Invalid scope override"):
            ctx.get_field(
                "total",
                SandboxContext(
                    {"activity-id": "other", "course-id": None, "user-id": None}
                ),
            )

    def test_scope_override_user_id_on_non_user_scoped_raises(
        self, tmp_path: Path
    ) -> None:
        """Should raise FieldValidationError when passing user_id on activity-scoped field."""
        manifest = create_manifest(
            fields={"question": {"type": "string", "scope": "activity", "default": ""}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        with pytest.raises(FieldValidationError, match="Invalid scope override"):
            ctx.get_field(
                "question",
                SandboxContext(
                    {"activity-id": None, "course-id": None, "user-id": "bob"}
                ),
            )
