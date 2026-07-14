"""Tests for the m2l6-visual-story sample activity.

Does not exercise the real Anthropic call (no network in CI) — only the
structural validation/gating paths: default state, credentials save, draft
save validation, and submit-before-a-valid-draft rejection.
"""

import pytest

from pxc.lib.actions import ActionValidationError
from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime

SLUG = "m2l6-visual-story"

APPROVED_TOPIC = "A day in the life of a future city"

VALID_IMAGES = [
    {"prompt": "Subject: ... Style: ... Composition: ... Mood: ... Context: ...", "caption": "Caption " + str(i)}
    for i in range(1, 4)
]


def test_get_state_play_mode_defaults() -> None:
    rt = make_runtime(SLUG)
    state = rt.get_state()
    assert state["topic"] == ""
    assert state["images"] == []
    assert state["submitted"] is False
    assert state["grade_result"] == {}
    assert APPROVED_TOPIC in state["approved_topics"]


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


def test_story_save_rejects_unapproved_topic() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("story.save", {"topic": "My custom topic", "images": VALID_IMAGES})
    assert rt.get_state()["topic"] == ""


def test_story_save_rejects_wrong_image_count() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("story.save", {"topic": APPROVED_TOPIC, "images": VALID_IMAGES[:2]})
    assert rt.get_state()["topic"] == ""


def test_story_save_rejects_missing_caption() -> None:
    rt = make_runtime(SLUG)
    images = [dict(img) for img in VALID_IMAGES]
    images[0]["caption"] = ""
    rt.on_action("story.save", {"topic": APPROVED_TOPIC, "images": images})
    assert rt.get_state()["topic"] == ""


def test_story_save_accepts_valid_draft() -> None:
    rt = make_runtime(SLUG, user_id="alice")
    rt.on_action("story.save", {"topic": APPROVED_TOPIC, "images": VALID_IMAGES})
    state = rt.get_state()
    assert state["topic"] == APPROVED_TOPIC
    assert len(state["images"]) == 3
    events = rt.clear_pending_events()
    assert len(events) == 1
    assert events[0]["context"]["user_id"] == "alice"


def test_submit_rejects_without_saved_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("story.submit", {})
    assert rt.get_state()["submitted"] is False


def test_submit_rejects_without_api_key_even_with_valid_draft() -> None:
    rt = make_runtime(SLUG)
    rt.on_action("story.save", {"topic": APPROVED_TOPIC, "images": VALID_IMAGES})
    rt.on_action("story.submit", {})
    assert rt.get_state()["submitted"] is False


def test_actions_rejected_in_view_permission() -> None:
    rt = make_runtime(SLUG, permission=Permission.view)
    with pytest.raises(ActionValidationError):
        rt.on_action("story.submit", {})
