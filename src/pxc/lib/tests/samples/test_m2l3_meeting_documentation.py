"""Tests for the m2l3-meeting-documentation sample activity.

Does not exercise the real Anthropic call (no network in CI) — only the
local validation/gating paths: default state, credentials save, and the
guard rails that reject generate/submit before their preconditions are met.
"""

import pytest

from pxc.lib.actions import ActionValidationError
from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime

SLUG = "m2l3-meeting-documentation"


def test_get_state_play_mode_defaults() -> None:
    rt = make_runtime(SLUG)
    state = rt.get_state()
    assert state["transcript_text"] == ""
    assert state["prompt_text"] == ""
    assert state["output_text"] == ""
    assert state["refinement_note"] == ""
    assert state["attempt_count"] == 0
    assert state["submitted"] is False
    assert state["grade_result"] == {}


def test_get_state_edit_mode_hides_key() -> None:
    rt = make_runtime(SLUG, permission=Permission.edit)
    state = rt.get_state()
    assert state["credentials_configured"] is False
    assert "haiku_api_key" not in state


def test_credentials_save_requires_edit_permission() -> None:
    rt = make_runtime(SLUG, permission=Permission.play)
    rt.on_action("credentials.save", {"haiku_api_key": "sk-ant-test"})
    rt.permission = Permission.edit
    assert rt.get_state()["credentials_configured"] is False


def test_credentials_save() -> None:
    rt = make_runtime(SLUG, permission=Permission.edit)
    rt.on_action("credentials.save", {"haiku_api_key": "sk-ant-test"})
    assert rt.get_state()["credentials_configured"] is True


def test_generate_event_is_scoped_to_calling_user_not_broadcast() -> None:
    rt = make_runtime(SLUG, user_id="alice")
    rt.on_action("meeting.generate", {"transcript": "notes", "prompt": "do it"})
    events = rt.clear_pending_events()
    assert len(events) == 1
    assert events[0]["context"]["user_id"] == "alice"


def test_generate_rejects_without_transcript() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("meeting.generate", {"transcript": "", "prompt": "do it"})
    assert rt.get_state()["attempt_count"] == 0


def test_generate_rejects_without_prompt() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("meeting.generate", {"transcript": "some notes", "prompt": "  "})
    assert rt.get_state()["attempt_count"] == 0


def test_generate_rejects_without_api_key() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("meeting.generate", {"transcript": "some notes", "prompt": "do it"})
    state = rt.get_state()
    assert state["attempt_count"] == 0
    assert state["output_text"] == ""


def test_save_refinement_note() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("meeting.save_refinement", "Added named owners to each decision.")
    assert rt.get_state()["refinement_note"] == "Added named owners to each decision."


def test_submit_rejects_before_min_attempts() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("meeting.save_refinement", "changed the format")
    rt.on_action("meeting.submit", {})
    state = rt.get_state()
    assert state["submitted"] is False
    assert state["grade_result"] == {}


def test_submit_rejects_without_refinement_note() -> None:
    rt = make_runtime(SLUG)
    # Can't reach 2 real attempts without a network call; just confirm the
    # refinement-note gate independently rejects at 0 attempts too.
    rt.on_action("meeting.submit", {})
    state = rt.get_state()
    assert state["submitted"] is False


def test_actions_rejected_in_view_permission() -> None:
    rt = make_runtime(SLUG, permission=Permission.view)
    with pytest.raises(ActionValidationError):
        rt.on_action("meeting.save_refinement", "note")
