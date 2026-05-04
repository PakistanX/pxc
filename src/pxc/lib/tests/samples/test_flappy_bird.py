"""Tests for the flappy-bird sample activity."""

import json
from typing import Any

from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime


def test_get_state_defaults() -> None:
    rt = make_runtime("flappy-bird")
    state = rt.get_state()
    assert state["best_score"] == 0
    assert state["top_scores"] == []


def test_game_over_updates_scores() -> None:
    rt = make_runtime("flappy-bird")
    rt.on_action("game.over", {"score": 5})
    state = rt.get_state()
    assert state["best_score"] == 5
    scores: list[Any] = state["top_scores"]  # type: ignore[assignment]
    assert len(scores) == 1
    assert scores[0]["score"] == 5


def test_scores_delete_removes_entry() -> None:
    rt = make_runtime("flappy-bird")
    rt.on_action("game.over", {"score": 10})
    rt.on_action("game.over", {"score": 20})
    rt.on_action("game.over", {"score": 15})
    rt.clear_pending_events()

    rt.permission = Permission.edit
    rt.on_action("scores.delete", 0)
    events = rt.clear_pending_events()

    state = rt.get_state()
    scores: list[Any] = state["top_scores"]  # type: ignore[assignment]
    assert len(scores) == 2
    # The top entry (score=20) was deleted; remaining are 15, 10
    assert scores[0]["score"] == 15
    assert scores[1]["score"] == 10

    change_events = [e for e in events if e["name"] == "fields.change.top_scores"]
    assert len(change_events) == 1
    updated = json.loads(change_events[0]["value"])
    assert len(updated) == 2


def test_scores_delete_ignored_in_play_mode() -> None:
    rt = make_runtime("flappy-bird")
    rt.on_action("game.over", {"score": 10})
    rt.clear_pending_events()

    rt.on_action("scores.delete", 0)
    scores: list[Any] = rt.get_state()["top_scores"]  # type: ignore[assignment]
    assert len(scores) == 1


def test_scores_delete_out_of_range() -> None:
    rt = make_runtime("flappy-bird")
    rt.on_action("game.over", {"score": 10})
    rt.clear_pending_events()

    rt.permission = Permission.edit
    rt.on_action("scores.delete", 5)
    scores: list[Any] = rt.get_state()["top_scores"]  # type: ignore[assignment]
    assert len(scores) == 1
