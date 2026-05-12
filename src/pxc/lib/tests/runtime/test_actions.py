from pathlib import Path

import pytest

from pxc.lib.actions import ActionValidationError
from pxc.lib.permission import Permission

from .utils import create_manifest, make_activity_runtime


class TestOnAction:
    """Tests for on_action method."""

    def test_raises_in_view_mode(self, tmp_path: Path) -> None:
        """Should raise ActionValidationError when permission is view."""
        manifest = create_manifest(
            actions={"answer.submit": {"type": "object", "properties": {}}}
        )
        ctx = make_activity_runtime(tmp_path, manifest, permission=Permission.view)

        with pytest.raises(ActionValidationError, match="view mode"):
            ctx.on_action("answer.submit", {})

    def test_raises_in_view_mode_regardless_of_action(self, tmp_path: Path) -> None:
        """Should raise for any action in view mode, even undeclared ones."""
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest, permission=Permission.view)

        with pytest.raises(ActionValidationError, match="view mode"):
            ctx.on_action("any.action", {})

    def test_allowed_in_play_mode(self, tmp_path: Path) -> None:
        """Should not raise for declared action in play mode."""
        manifest = create_manifest(
            actions={"answer.submit": {"type": "object", "properties": {}}}
        )
        ctx = make_activity_runtime(tmp_path, manifest, permission=Permission.play)
        ctx.on_action("answer.submit", {})
