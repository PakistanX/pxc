"""Tests for the essay sample activity."""

import json
from typing import Any, cast

from pxc.lib.permission import Permission
from pxc.lib.runtime import PendingEvent
from pxc.lib.tests.samples.conftest import make_runtime


def _saved_event_count(events: list[PendingEvent], name: str) -> int:
    return sum(1 for e in events if e["name"] == name)


def _events_by_name(events: list[PendingEvent], name: str) -> list[PendingEvent]:
    return [e for e in events if e["name"] == name]


def _as_dict(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value)


def test_get_state_defaults_play() -> None:
    rt = make_runtime("essay", permission=Permission.play)
    state = rt.get_state()
    assert state["instructions"] == ""
    assert state["draft"] == ""
    assert state["submission"] is None
    assert "criteria" not in state


def test_get_state_defaults_view() -> None:
    rt = make_runtime("essay", permission=Permission.view)
    state = rt.get_state()
    assert state == {"instructions": ""}


def test_get_state_defaults_edit() -> None:
    rt = make_runtime("essay", permission=Permission.edit)
    state = rt.get_state()
    assert state["instructions"] == ""
    assert state["criteria"] == ""
    assert state["submissions"] == []


def test_config_save() -> None:
    rt = make_runtime("essay", permission=Permission.edit)
    rt.on_action(
        "config.save",
        {
            "instructions": "Write a short essay about X.",
            "criteria": "Look for clarity and depth.",
        },
    )
    state = rt.get_state()
    assert state["instructions"] == "Write a short essay about X."
    assert state["criteria"] == "Look for clarity and depth."
    events = rt.clear_pending_events()
    names = [e["name"] for e in events]
    assert "fields.change.instructions" in names
    assert "fields.change.criteria" in names


def test_play_cannot_see_criteria() -> None:
    rt = make_runtime("essay", permission=Permission.edit)
    rt.on_action("config.save", {"instructions": "Inst.", "criteria": "Secret rubric."})
    rt.permission = Permission.play
    state = rt.get_state()
    assert "criteria" not in state
    assert state["instructions"] == "Inst."


def test_essay_save_draft() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.save", "My draft text.")
    state = rt.get_state()
    assert state["draft"] == "My draft text."
    assert state["submission"] is None
    events = rt.clear_pending_events()
    saved = _events_by_name(events, "essay.saved")
    assert len(saved) == 1
    assert json.loads(saved[0]["value"]) is True


def test_essay_save_overwrites_draft() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.save", "First draft.")
    rt.on_action("essay.save", "Second draft.")
    state = rt.get_state()
    assert state["draft"] == "Second draft."


def test_essay_submit() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.submit", "My final essay.")
    state = rt.get_state()
    assert state["submission"] is not None
    submission = _as_dict(state["submission"])
    assert submission["text"] == "My final essay."
    assert submission["status"] == "submitted"
    assert submission["user_id"] == "alice"
    events = rt.clear_pending_events()
    assert _saved_event_count(events, "essay.submitted") == 1
    assert _saved_event_count(events, "submissions.changed") == 1


def test_essay_save_rejected_after_submit() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.save", "Draft before submit.")
    rt.on_action("essay.submit", "Final text.")
    rt.clear_pending_events()
    rt.on_action("essay.save", "Attempt after submit.")
    state = rt.get_state()
    # Draft is the submitted text (submit syncs draft) and is not changed by post-submit saves
    assert state["draft"] == "Final text."
    assert _as_dict(state["submission"])["text"] == "Final text."
    events = rt.clear_pending_events()
    assert _saved_event_count(events, "essay.saved") == 0


def test_unsubmit_restores_draft_when_student_submitted_without_saving() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    # Student types into the textarea and clicks Submit without ever clicking Save
    rt.on_action("essay.submit", "Direct submission text.")
    rt.clear_pending_events()

    rt.user_id = "instructor"
    rt.permission = Permission.edit
    rt.on_action("essay.unsubmit", {"user_id": "alice"})

    rt.user_id = "alice"
    rt.permission = Permission.play
    state = rt.get_state()
    # Their submitted text is preserved as the draft so they can keep editing
    assert state["submission"] is None
    assert state["draft"] == "Direct submission text."


def test_essay_submit_twice_rejected() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.submit", "First submission.")
    rt.clear_pending_events()
    rt.on_action("essay.submit", "Second submission attempt.")
    state = rt.get_state()
    assert _as_dict(state["submission"])["text"] == "First submission."
    # No new submission event
    events = rt.clear_pending_events()
    assert _saved_event_count(events, "essay.submitted") == 0


def test_essay_grade() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.submit", "Alice's essay.")
    rt.clear_pending_events()

    rt.user_id = "instructor"
    rt.permission = Permission.edit
    rt.on_action(
        "essay.grade",
        {"user_id": "alice", "grade": 0.85, "grade_comment": "Well done!"},
    )

    events = rt.clear_pending_events()
    graded = _events_by_name(events, "essay.graded")
    assert len(graded) == 1
    payload = json.loads(graded[0]["value"])
    assert payload["grade"] == 0.85
    assert payload["grade_comment"] == "Well done!"

    # The graded event is targeted at alice
    assert graded[0]["context"].get("user_id") == "alice"

    # Editor sees the updated submission
    edit_state = rt.get_state()
    subs: list[dict[str, Any]] = edit_state["submissions"]  # type: ignore[assignment]
    assert len(subs) == 1
    assert subs[0]["value"]["status"] == "graded"
    assert subs[0]["value"]["grade"] == 0.85
    assert subs[0]["value"]["grade_comment"] == "Well done!"

    # Alice sees her grade
    rt.user_id = "alice"
    rt.permission = Permission.play
    alice_state = rt.get_state()
    alice_sub = _as_dict(alice_state["submission"])
    assert alice_sub["status"] == "graded"
    assert alice_sub["grade"] == 0.85
    assert alice_sub["grade_comment"] == "Well done!"


def test_essay_grade_no_submission_noop() -> None:
    rt = make_runtime("essay", permission=Permission.edit, user_id="instructor")
    rt.on_action(
        "essay.grade",
        {"user_id": "ghost", "grade": 0.5, "grade_comment": ""},
    )
    state = rt.get_state()
    assert state["submissions"] == []
    events = rt.clear_pending_events()
    assert _saved_event_count(events, "essay.graded") == 0


def test_essay_unsubmit() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.save", "My draft.")
    rt.on_action("essay.submit", "Final essay.")
    rt.clear_pending_events()

    rt.user_id = "instructor"
    rt.permission = Permission.edit
    rt.on_action("essay.unsubmit", {"user_id": "alice"})
    events = rt.clear_pending_events()
    assert _saved_event_count(events, "submissions.changed") == 1

    edit_state = rt.get_state()
    assert edit_state["submissions"] == []

    # Alice can edit again; her draft is preserved
    rt.user_id = "alice"
    rt.permission = Permission.play
    alice_state = rt.get_state()
    assert alice_state["submission"] is None
    assert alice_state["draft"] == "Final essay."

    # And she can save a new draft
    rt.on_action("essay.save", "Revised draft.")
    state2 = rt.get_state()
    assert state2["draft"] == "Revised draft."


def test_essay_unsubmit_after_grade() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.submit", "Alice essay.")
    rt.clear_pending_events()

    rt.user_id = "instructor"
    rt.permission = Permission.edit
    rt.on_action(
        "essay.grade",
        {"user_id": "alice", "grade": 0.7, "grade_comment": "OK"},
    )
    rt.on_action("essay.unsubmit", {"user_id": "alice"})
    state = rt.get_state()
    assert state["submissions"] == []


def test_essay_delete() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.save", "My draft.")
    rt.on_action("essay.submit", "Alice essay.")
    rt.clear_pending_events()

    rt.user_id = "instructor"
    rt.permission = Permission.edit
    rt.on_action("essay.delete", {"user_id": "alice"})
    events = rt.clear_pending_events()
    assert _saved_event_count(events, "submissions.changed") == 1

    edit_state = rt.get_state()
    assert edit_state["submissions"] == []

    # Alice's draft is also cleared
    rt.user_id = "alice"
    rt.permission = Permission.play
    alice_state = rt.get_state()
    assert alice_state["submission"] is None
    assert alice_state["draft"] == ""


def test_essay_delete_no_submission_clears_draft() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.save", "Just a draft.")
    rt.clear_pending_events()

    rt.user_id = "instructor"
    rt.permission = Permission.edit
    rt.on_action("essay.delete", {"user_id": "alice"})

    rt.user_id = "alice"
    rt.permission = Permission.play
    state = rt.get_state()
    assert state["draft"] == ""
    assert state["submission"] is None


def test_get_state_edit_shows_all_submissions() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.submit", "Alice essay.")
    rt.user_id = "bob"
    rt.on_action("essay.submit", "Bob essay.")
    rt.clear_pending_events()

    rt.permission = Permission.edit
    state = rt.get_state()
    subs: list[dict[str, Any]] = state["submissions"]  # type: ignore[assignment]
    assert len(subs) == 2
    user_ids = {s["value"]["user_id"] for s in subs}
    assert user_ids == {"alice", "bob"}


def test_grade_then_regrade() -> None:
    rt = make_runtime("essay", permission=Permission.play, user_id="alice")
    rt.on_action("essay.submit", "Alice essay.")
    rt.clear_pending_events()

    rt.user_id = "instructor"
    rt.permission = Permission.edit
    rt.on_action(
        "essay.grade",
        {"user_id": "alice", "grade": 0.5, "grade_comment": "First take"},
    )
    rt.on_action(
        "essay.grade",
        {"user_id": "alice", "grade": 0.9, "grade_comment": "Reconsidered"},
    )

    state = rt.get_state()
    subs: list[dict[str, Any]] = state["submissions"]  # type: ignore[assignment]
    assert len(subs) == 1
    assert subs[0]["value"]["grade"] == 0.9
    assert subs[0]["value"]["grade_comment"] == "Reconsidered"

    # Alice sees the latest grade
    rt.user_id = "alice"
    rt.permission = Permission.play
    alice_state = rt.get_state()
    assert _as_dict(alice_state["submission"])["grade"] == 0.9
