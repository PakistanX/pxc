"""Tests for the m1l8-email-prompt-craft sample activity.

Does not exercise the real Anthropic call (no network in CI) — only the
local validation/gating paths: default state, credentials save, scenario
selection, and the guard rails that reject generate/submit before their
preconditions are met.
"""

import pytest

from pxc.lib.actions import ActionValidationError
from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime


def test_get_state_play_mode_defaults() -> None:
    rt = make_runtime("m1l8-email-prompt-craft")
    state = rt.get_state()
    assert state["scenario"] == ""
    assert state["prompt_text"] == ""
    assert state["output_text"] == ""
    assert state["attempt_count"] == 0
    assert state["submitted"] is False
    assert state["grade_result"] == {}
    assert "client_followup" in state["scenarios"]


def test_get_state_edit_mode_hides_key() -> None:
    rt = make_runtime("m1l8-email-prompt-craft", permission=Permission.edit)
    state = rt.get_state()
    assert state["credentials_configured"] is False
    assert "haiku_api_key" not in state


def test_credentials_save_requires_edit_permission() -> None:
    rt = make_runtime("m1l8-email-prompt-craft", permission=Permission.play)
    rt.on_action("credentials.save", {"haiku_api_key": "sk-ant-test"})
    rt.permission = Permission.edit
    assert rt.get_state()["credentials_configured"] is False


def test_credentials_save() -> None:
    rt = make_runtime("m1l8-email-prompt-craft", permission=Permission.edit)
    rt.on_action("credentials.save", {"haiku_api_key": "sk-ant-test"})
    assert rt.get_state()["credentials_configured"] is True


def test_scenario_select() -> None:
    rt = make_runtime("m1l8-email-prompt-craft")
    rt.on_action("scenario.select", "cold_outreach")
    assert rt.get_state()["scenario"] == "cold_outreach"


def test_scenario_select_event_is_scoped_to_calling_user_not_broadcast() -> None:
    # Regression test: per-user events must target { userId } — "broadcast"
    # (empty/no user_id in context) would leak one student's scenario/prompt/
    # output/grade into every classmate polling the same activity_id.
    rt = make_runtime("m1l8-email-prompt-craft", user_id="alice")
    rt.on_action("scenario.select", "cold_outreach")
    events = rt.clear_pending_events()
    assert len(events) == 1
    assert events[0]["context"]["user_id"] == "alice"


def test_generate_error_event_is_scoped_to_calling_user() -> None:
    rt = make_runtime("m1l8-email-prompt-craft", user_id="bob")
    rt.on_action("email.generate", "Write me an email.")  # no scenario selected -> error event
    events = rt.clear_pending_events()
    assert len(events) == 1
    assert events[0]["name"] == "generation.error"
    assert events[0]["context"]["user_id"] == "bob"


def test_scenario_select_rejects_unknown_scenario() -> None:
    rt = make_runtime("m1l8-email-prompt-craft")
    rt.on_action("scenario.select", "not_a_real_scenario")
    assert rt.get_state()["scenario"] == ""


def test_generate_rejects_without_scenario() -> None:
    rt = make_runtime("m1l8-email-prompt-craft")
    rt.on_action("email.generate", "Write me an email.")
    state = rt.get_state()
    assert state["attempt_count"] == 0
    assert state["output_text"] == ""


def test_generate_rejects_without_prompt() -> None:
    rt = make_runtime("m1l8-email-prompt-craft")
    rt.on_action("scenario.select", "team_intro")
    rt.on_action("email.generate", "   ")
    assert rt.get_state()["attempt_count"] == 0


def test_generate_rejects_without_api_key() -> None:
    rt = make_runtime("m1l8-email-prompt-craft")
    rt.on_action("scenario.select", "team_intro")
    rt.on_action("email.generate", "Write me an email.")
    state = rt.get_state()
    # No key configured for this course scope -> no HTTP call attempted, no state written.
    assert state["attempt_count"] == 0
    assert state["output_text"] == ""


def test_submit_rejects_before_min_attempts() -> None:
    rt = make_runtime("m1l8-email-prompt-craft")
    rt.on_action("scenario.select", "team_intro")
    rt.on_action("email.submit", {})
    state = rt.get_state()
    assert state["submitted"] is False
    assert state["grade_result"] == {}


def test_actions_rejected_in_view_permission() -> None:
    rt = make_runtime("m1l8-email-prompt-craft", permission=Permission.view)
    with pytest.raises(ActionValidationError):
        rt.on_action("scenario.select", "team_intro")
