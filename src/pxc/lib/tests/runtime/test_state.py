from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pxc.lib.runtime import ActivityRuntime
from pxc.lib.sandbox import SandboxRuntimeError
from pxc.lib.file_storage import MemoryFileStorage
from pxc.lib.permission import Permission

from .utils import (
    create_manifest,
    make_field_store,
    setup_activity_dir,
    make_activity_runtime,
)


class TestGetState:
    """Tests for get_state method."""

    def test_fallback_without_sandbox(self, tmp_path: Path) -> None:
        """Should fall back to get_all_fields when no sandbox exists."""
        manifest = create_manifest(
            fields={
                "score": {
                    "type": "integer",
                    "scope": "user,activity",
                    "default": 0,
                },
            }
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.user_id = "alice"

        result = ctx.get_state()
        assert result == {"score": 0}

    @patch("pxc.lib.sandbox.SandboxComponentExecutor")
    def test_calls_sandbox_get_state(
        self, mock_sandbox_class: MagicMock, tmp_path: Path
    ) -> None:
        """Should call sandbox get-state when available."""
        manifest = create_manifest(sandbox="sandbox.wasm")
        activity_dir = setup_activity_dir(tmp_path, manifest)
        (activity_dir / "sandbox.wasm").write_bytes(b"fake wasm")

        mock_sandbox = MagicMock()
        mock_sandbox.call_function.return_value = b'{"question": "test"}'
        mock_sandbox_class.return_value = mock_sandbox

        ctx = ActivityRuntime(
            activity_dir,
            make_field_store(),
            MemoryFileStorage(),
            "myactivity",
            "mycourse",
            "myuser",
            Permission.play,
        )
        result = ctx.get_state()

        expected_input = [
            {"user-id": "myuser", "course-id": "mycourse", "activity-id": "myactivity"},
            "play",
        ]
        mock_sandbox.call_function.assert_called_once_with("get-state", *expected_input)
        assert result == {"question": "test"}

    @patch("pxc.lib.sandbox.SandboxComponentExecutor")
    def test_no_fallback_on_runtime_error(
        self, mock_sandbox_class: MagicMock, tmp_path: Path
    ) -> None:
        """Should raise error when get-state raises SandboxRuntimeError."""
        manifest = create_manifest(
            sandbox="sandbox.wasm",
            fields={
                "score": {
                    "type": "integer",
                    "scope": "user,activity",
                    "default": 0,
                },
            },
        )
        activity_dir = setup_activity_dir(tmp_path, manifest)
        (activity_dir / "sandbox.wasm").write_bytes(b"fake wasm")

        mock_sandbox = MagicMock()
        mock_sandbox.call_function.side_effect = SandboxRuntimeError(
            "get-state not found"
        )
        mock_sandbox_class.return_value = mock_sandbox

        ctx = ActivityRuntime(
            activity_dir,
            make_field_store(),
            MemoryFileStorage(),
            "activityid",
            "courseid",
            "alice",
            Permission.play,
        )
        with pytest.raises(SandboxRuntimeError, match="get-state not found"):
            ctx.get_state()


class TestGetUsernames:
    """Tests for get_usernames host function."""

    def test_default_returns_id_tuples(self, tmp_path: Path) -> None:
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest)
        assert ctx.get_usernames(["u1", "u2"]) == [("u1", "u1"), ("u2", "u2")]

    def test_default_empty_input(self, tmp_path: Path) -> None:
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest)
        assert ctx.get_usernames([]) == []

    def test_default_preserves_input_order(self, tmp_path: Path) -> None:
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest)
        assert ctx.get_usernames(["c", "a", "b"]) == [
            ("c", "c"),
            ("a", "a"),
            ("b", "b"),
        ]

    def test_subclass_can_override(self, tmp_path: Path) -> None:
        class CustomRuntime(ActivityRuntime):
            def get_usernames(self, ids: list[str]) -> list[tuple[str, str]]:
                names = {"alice": "Alice A.", "bob": "Bob B."}
                return [(uid, names.get(uid, uid)) for uid in ids]

        manifest = create_manifest()
        activity_dir = setup_activity_dir(tmp_path, manifest)
        ctx = CustomRuntime(
            activity_dir,
            make_field_store(),
            MemoryFileStorage(),
            "activityid",
            "courseid",
            "userid",
            Permission.play,
        )
        assert ctx.get_usernames(["alice", "unknown"]) == [
            ("alice", "Alice A."),
            ("unknown", "unknown"),
        ]
