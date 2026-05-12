from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pxc.lib.capabilities import CapabilityError
from pxc.lib.runtime import ActivityRuntime
from pxc.lib.file_storage import MemoryFileStorage
from pxc.lib.permission import Permission

from .utils import (
    create_manifest,
    make_field_store,
    setup_activity_dir,
    make_activity_runtime,
)


class TestActivityRuntimeInit:
    """Tests for ActivityRuntime initialization."""

    def test_init_creates_field_store(self, tmp_path: Path) -> None:
        """Should create a KV store at the expected path."""
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest)

        assert ctx.field_store is not None

    def test_init_loads_manifest(self, tmp_path: Path) -> None:
        """Should load manifest from activity directory."""
        manifest = create_manifest("my-activity", {"http": {}})
        ctx = make_activity_runtime(tmp_path, manifest)

        assert ctx.manifest.name == "my-activity"
        assert ctx.manifest.capabilities is not None
        assert ctx.manifest.capabilities.http is not None

    def test_init_creates_capability_checker(self, tmp_path: Path) -> None:
        """Should create a CapabilityChecker from manifest."""
        manifest = create_manifest(capabilities={"http": {}})
        ctx = make_activity_runtime(tmp_path, manifest)

        assert ctx.capability_checker is not None
        with pytest.raises(CapabilityError):
            ctx.capability_checker.check_http_request("https://example.com")

    def test_init_without_sandbox(self, tmp_path: Path) -> None:
        """Should set sandbox to None when no wasm file exists."""
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest)

        assert ctx.sandbox is None

    @patch("pxc.lib.sandbox.SandboxComponentExecutor")
    def test_init_with_sandbox(
        self, mock_sandbox_executor: MagicMock, tmp_path: Path
    ) -> None:
        """Should create SandboxComponentExecutor when server is declared in manifest."""
        manifest = create_manifest(sandbox="sandbox.wasm")
        activity_dir = setup_activity_dir(tmp_path, manifest)
        (activity_dir / "sandbox.wasm").write_bytes(b"fake wasm")

        ctx = ActivityRuntime(
            activity_dir,
            make_field_store(),
            MemoryFileStorage(),
            "activityid",
            "courseid",
            "userid",
            Permission.play,
        )

        mock_sandbox_executor.assert_called_once()
        assert ctx.sandbox is not None


class TestActivityRuntimeProperties:
    """Tests for ActivityRuntime properties."""

    def test_name_property(self, tmp_path: Path) -> None:
        """Should return the activity name from manifest."""
        manifest = create_manifest("quiz-activity")
        ctx = make_activity_runtime(tmp_path, manifest)

        assert ctx.name == "quiz-activity"

    def test_ui_path_property(self, tmp_path: Path) -> None:
        """Should return UI path from manifest."""
        manifest = create_manifest(ui="src/my-ui.js")
        ctx = make_activity_runtime(tmp_path, manifest)

        assert ctx.ui_path == "src/my-ui.js"


class TestHostFunctions:
    """Tests for host_functions method — grouped by WIT interface."""

    def test_state_only_by_default(self, tmp_path: Path) -> None:
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest)

        interfaces = ctx.host_functions()

        assert list(interfaces.keys()) == ["state"]
        assert sorted(interfaces["state"].keys()) == [
            "get-field",
            "get-usernames",
            "log-append",
            "log-delete",
            "log-delete-range",
            "log-get",
            "log-get-range",
            "send-event",
            "set-field",
        ]

    def test_grading_interface_when_declared(self, tmp_path: Path) -> None:
        manifest = create_manifest(capabilities={"grading": {}})
        ctx = make_activity_runtime(tmp_path, manifest)

        interfaces = ctx.host_functions()

        assert "grading" in interfaces
        assert sorted(interfaces["grading"].keys()) == [
            "report-completed",
            "report-failed",
            "report-passed",
            "report-progressed",
            "report-scored",
            "submit-grade",
        ]

    def test_http_interface_when_declared(self, tmp_path: Path) -> None:
        manifest = create_manifest(
            capabilities={"http": {"allowed_hosts": ["example.com"]}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        interfaces = ctx.host_functions()

        assert "http" in interfaces
        assert list(interfaces["http"].keys()) == ["http-request"]

    def test_storage_interface_when_declared(self, tmp_path: Path) -> None:
        manifest = create_manifest(
            capabilities={"storage": {"media": {"scope": "activity"}}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        interfaces = ctx.host_functions()

        assert "storage" in interfaces
        assert sorted(interfaces["storage"].keys()) == [
            "storage-delete",
            "storage-exists",
            "storage-list",
            "storage-read",
            "storage-url",
            "storage-write",
        ]
