"""Tests for NotebookActivityRuntime.storage_url override."""

from pxc.lib.permission import Permission
from pxc.lib.runtime import SandboxContext
from pxc.lib.signing import verify_token
from pxc.notebook import constants
from pxc.notebook.runtime import NotebookActivityRuntime


def _make_runtime(permission: Permission = Permission.play) -> NotebookActivityRuntime:
    return NotebookActivityRuntime(
        constants.SAMPLES_DIR / "image",
        activity_id="a1",
        course_id="c1",
        user_id="u1",
        permission=permission,
    )


def test_storage_url_is_token_prefixed() -> None:
    rt = _make_runtime()
    url = rt.storage_url("media", "img.png")
    expected_prefix = f"/_pxc/t/{rt._pxc_token}/activity/a1/storage/media/img.png"
    assert url == expected_prefix


def test_storage_url_token_encodes_claims() -> None:
    rt = _make_runtime(permission=Permission.edit)
    claims = verify_token(rt._pxc_token)
    assert claims["aid"] == "a1"
    assert claims["cid"] == "c1"
    assert claims["uid"] == "u1"
    assert claims["p"] == "edit"


def test_storage_url_preserves_context_overrides() -> None:
    rt = _make_runtime()
    ctx: SandboxContext = {
        "activity-id": None,
        "course-id": None,
        "user-id": "other-user",
    }
    url = rt.storage_url("media", "f.txt", ctx)
    assert url == (
        f"/_pxc/t/{rt._pxc_token}/activity/a1/storage/media/f.txt?user_id=other-user"
    )
