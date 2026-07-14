"""Tests for the m2l5-presentation-builder sample activity.

Does not exercise the real Anthropic call (no network in CI) — only the
structural validation/gating paths: default state, credentials save, draft
save validation, and submit-before-a-valid-draft rejection.
"""

import pytest

from pxc.lib.actions import ActionValidationError
from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime

SLUG = "m2l5-presentation-builder"

APPROVED_TOPIC = "Smart Cities and the Future of Urban Living"

VALID_STAGES = [
    {"label": "Outline", "text": "Plan a slide-by-slide outline."},
    {"label": "Content", "text": "Write bullet points for each slide."},
    {"label": "Speaker Notes", "text": "Write notes for each slide."},
]

VALID_SLIDES = [
    {"title": "Slide " + str(i), "bullets": ["a", "b", "c"], "notes": "notes " + str(i)}
    for i in range(1, 6)
]


def test_get_state_play_mode_defaults() -> None:
    rt = make_runtime(SLUG)
    state = rt.get_state()
    assert state["topic"] == ""
    assert state["prompt_stages"] == []
    assert state["slides"] == []
    assert state["submitted"] is False
    assert state["grade_result"] == {}
    assert "Smart Cities and the Future of Urban Living" in state["approved_topics"]


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


def test_deck_save_rejects_unapproved_topic() -> None:
    rt = make_runtime(SLUG)
    rt.on_action(
        "deck.save",
        {"topic": "My custom topic", "prompt_stages": VALID_STAGES, "slides": VALID_SLIDES},
    )
    assert rt.get_state()["topic"] == ""


def test_deck_save_rejects_fewer_than_3_stages() -> None:
    rt = make_runtime(SLUG)
    rt.on_action(
        "deck.save",
        {"topic": APPROVED_TOPIC, "prompt_stages": VALID_STAGES[:2], "slides": VALID_SLIDES},
    )
    assert rt.get_state()["topic"] == ""


def test_deck_save_rejects_wrong_slide_count() -> None:
    rt = make_runtime(SLUG)
    rt.on_action(
        "deck.save",
        {"topic": APPROVED_TOPIC, "prompt_stages": VALID_STAGES, "slides": VALID_SLIDES[:4]},
    )
    assert rt.get_state()["topic"] == ""


def test_deck_save_accepts_valid_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action(
        "deck.save",
        {"topic": APPROVED_TOPIC, "prompt_stages": VALID_STAGES, "slides": VALID_SLIDES},
    )
    state = rt.get_state()
    assert state["topic"] == APPROVED_TOPIC
    assert len(state["prompt_stages"]) == 3
    assert len(state["slides"]) == 5
    events = rt.clear_pending_events()
    assert len(events) == 1
    assert events[0]["context"]["user_id"] == "u1"


def test_submit_rejects_without_saved_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("deck.submit", {})
    assert rt.get_state()["submitted"] is False


def test_submit_rejects_without_api_key_even_with_valid_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action(
        "deck.save",
        {"topic": APPROVED_TOPIC, "prompt_stages": VALID_STAGES, "slides": VALID_SLIDES},
    )
    rt.on_action("deck.submit", {})
    assert rt.get_state()["submitted"] is False


def test_actions_rejected_in_view_permission() -> None:
    rt = make_runtime(SLUG, permission=Permission.view)
    with pytest.raises(ActionValidationError):
        rt.on_action("deck.submit", {})
