"""Tests for the m3l2-data-analysis-toolkit sample activity.

Does not exercise the real Anthropic call (no network in CI) — only the
structural validation/gating paths: default state, credentials save, draft
save validation, and submit-before-a-valid-draft rejection.
"""

import pytest

from pxc.lib.actions import ActionValidationError
from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime

SLUG = "m3l2-data-analysis-toolkit"

APPROVED_DATASET = "Website Analytics"

VALID_VISUALIZATIONS = [
    {"title": "Paid Search Drives 3x More Conversions", "caption": "Paid Search averages 87 conversions vs 28 for Organic."},
    {"title": "Mobile Bounce Rate Nearly Double Desktop's", "caption": "Mobile bounce (0.61) vs Desktop (0.33) signals a UX gap."},
]


def _valid_draft():
    return {
        "dataset": APPROVED_DATASET,
        "ai_description": "250 rows, 10 columns: date, page, sessions, conversions. No missing values.",
        "visualizations": VALID_VISUALIZATIONS,
        "executive_summary": "Paid Search drives more conversions than Organic. Increase budget by 20%.",
        "stage2_prompt": "You are a senior data analyst. Calculate mean, median, stdev, min, max.",
        "stage3_prompt": "Based on the statistics above, what are the 2 most important findings?",
        "stage4_prompt": "Create 2 charts for a management presentation with interpretive captions.",
    }


def test_get_state_play_mode_defaults() -> None:
    rt = make_runtime(SLUG)
    state = rt.get_state()
    assert state["dataset"] == ""
    assert state["ai_description"] == ""
    assert state["visualizations"] == []
    assert state["executive_summary"] == ""
    assert state["stage2_prompt"] == ""
    assert state["stage3_prompt"] == ""
    assert state["stage4_prompt"] == ""
    assert state["submitted"] is False
    assert state["grade_result"] == {}
    assert "Website Analytics" in state["approved_datasets"]


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


def test_draft_save_rejects_unapproved_dataset() -> None:
    rt = make_runtime(SLUG)
    draft = _valid_draft()
    draft["dataset"] = "My custom dataset"
    rt.on_action("draft.save", draft)
    assert rt.get_state()["dataset"] == ""


def test_draft_save_rejects_wrong_visualization_count() -> None:
    rt = make_runtime(SLUG)
    draft = _valid_draft()
    draft["visualizations"] = VALID_VISUALIZATIONS[:1]
    rt.on_action("draft.save", draft)
    assert rt.get_state()["dataset"] == ""


def test_draft_save_rejects_visualization_missing_caption() -> None:
    rt = make_runtime(SLUG)
    draft = _valid_draft()
    draft["visualizations"] = [{"title": "Viz 1", "caption": ""}, VALID_VISUALIZATIONS[1]]
    rt.on_action("draft.save", draft)
    assert rt.get_state()["dataset"] == ""


def test_draft_save_rejects_missing_stage_prompt() -> None:
    rt = make_runtime(SLUG)
    draft = _valid_draft()
    draft["stage4_prompt"] = ""
    rt.on_action("draft.save", draft)
    assert rt.get_state()["dataset"] == ""


def test_draft_save_accepts_valid_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("draft.save", _valid_draft())
    state = rt.get_state()
    assert state["dataset"] == APPROVED_DATASET
    assert len(state["visualizations"]) == 2
    events = rt.clear_pending_events()
    assert len(events) == 1
    assert events[0]["context"]["user_id"] == "u1"


def test_submit_rejects_without_saved_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("toolkit.submit", {})
    assert rt.get_state()["submitted"] is False


def test_submit_rejects_without_api_key_even_with_valid_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("draft.save", _valid_draft())
    rt.on_action("toolkit.submit", {})
    assert rt.get_state()["submitted"] is False


def test_actions_rejected_in_view_permission() -> None:
    rt = make_runtime(SLUG, permission=Permission.view)
    with pytest.raises(ActionValidationError):
        rt.on_action("toolkit.submit", {})
