"""Tests for the youtube sample activity."""

from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime


def test_get_state_defaults() -> None:
    rt = make_runtime("youtube")
    state = rt.get_state()
    assert state["video_id"] == ""
    assert state["start_time"] == 0


def test_get_state_edit_mode() -> None:
    rt = make_runtime("youtube", permission=Permission.edit)
    state = rt.get_state()
    assert "video_id" in state
    assert "start_time" in state


def test_config_save() -> None:
    rt = make_runtime("youtube", permission=Permission.edit)
    rt.on_action("config.save", {"video_id": "dQw4w9WgXcQ", "start_time": 30})
    state = rt.get_state()
    assert state["video_id"] == "dQw4w9WgXcQ"
    assert state["start_time"] == 30


def test_config_save_default_start_time() -> None:
    rt = make_runtime("youtube", permission=Permission.edit)
    rt.on_action("config.save", {"video_id": "dQw4w9WgXcQ"})
    state = rt.get_state()
    assert state["start_time"] == 0


def test_config_save_emits_event() -> None:
    rt = make_runtime("youtube", permission=Permission.edit)
    rt.on_action("config.save", {"video_id": "abc123", "start_time": 60})
    events = rt.clear_pending_events()
    names = [e["name"] for e in events]
    assert "fields.change.video_id" in names
    assert "fields.change.start_time" in names
