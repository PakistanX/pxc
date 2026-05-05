"""Tests for the flashcards sample activity."""

import json
import time
from typing import Any

from pxc.lib.field_store import MemoryKVStore
from pxc.lib.file_storage import MemoryFileStorage
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime
from pxc.lib.tests.samples.conftest import SAMPLES_DIR, make_runtime

DAY_MS = 86_400_000


def _seed_cards(rt: ActivityRuntime, *card_ids: str, rating_mode: str = "sm2") -> None:
    rt.permission = Permission.edit
    rt.on_action(
        "config.save",
        {
            "cards": [
                {"id": cid, "front": f"Q-{cid}", "back": f"A-{cid}"} for cid in card_ids
            ],
            "rating_mode": rating_mode,
        },
    )
    rt.clear_pending_events()
    rt.permission = Permission.play


def _schedule_for(rt: ActivityRuntime, card_id: str) -> dict[str, Any]:
    state = rt.get_state()
    schedule: list[dict[str, Any]] = state.get("schedule", [])  # type: ignore[assignment]
    matches = [entry for entry in schedule if entry["card_id"] == card_id]
    assert len(matches) == 1, f"expected one schedule entry for {card_id}"
    return matches[0]


def test_default_state() -> None:
    rt = make_runtime("flashcards")
    state = rt.get_state()
    assert state["cards"] == []
    assert state["rating_mode"] == "sm2"
    assert state["schedule"] == []


def test_view_mode_excludes_schedule() -> None:
    rt = make_runtime("flashcards", permission=Permission.view)
    state = rt.get_state()
    assert "schedule" not in state


def test_config_save_requires_edit() -> None:
    rt = make_runtime("flashcards", permission=Permission.play)
    rt.on_action(
        "config.save",
        {"cards": [{"id": "c1", "front": "f", "back": "b"}], "rating_mode": "binary"},
    )
    state = rt.get_state()
    assert state["cards"] == []
    assert state["rating_mode"] == "sm2"


def test_config_save_persists_and_emits_events() -> None:
    rt = make_runtime("flashcards", permission=Permission.edit)
    rt.on_action(
        "config.save",
        {
            "cards": [
                {"id": "c1", "front": "Front 1", "back": "Back 1"},
                {"id": "c2", "front": "Front 2", "back": "Back 2"},
            ],
            "rating_mode": "binary",
        },
    )
    events = rt.clear_pending_events()
    names = [e["name"] for e in events]
    assert "fields.change.cards" in names
    assert "fields.change.rating_mode" in names

    state = rt.get_state()
    cards: list[dict[str, Any]] = state["cards"]  # type: ignore[assignment]
    assert len(cards) == 2
    assert cards[0]["front"] == "Front 1"
    assert state["rating_mode"] == "binary"


def test_invalid_rating_mode_falls_back_to_sm2() -> None:
    rt = make_runtime("flashcards", permission=Permission.edit)
    rt.on_action(
        "config.save",
        {"cards": [{"id": "c1", "front": "f", "back": "b"}], "rating_mode": "foo"},
    )
    state = rt.get_state()
    assert state["rating_mode"] == "sm2"


def test_play_review_creates_schedule_entry() -> None:
    rt = make_runtime("flashcards")
    _seed_cards(rt, "c1")
    before = int(time.time() * 1000)
    rt.on_action("card.review", {"card_id": "c1", "rating": "good"})
    entry = _schedule_for(rt, "c1")
    assert entry["repetitions"] == 1
    assert entry["interval"] == 1
    assert entry["due_at"] >= before


def test_card_review_emits_schedule_change() -> None:
    rt = make_runtime("flashcards")
    _seed_cards(rt, "c1")
    rt.on_action("card.review", {"card_id": "c1", "rating": "good"})
    events = rt.clear_pending_events()
    schedule_events = [e for e in events if e["name"] == "fields.change.schedule"]
    assert len(schedule_events) == 1
    payload = json.loads(schedule_events[0]["value"])
    assert any(s["card_id"] == "c1" for s in payload)


def test_sm2_progression() -> None:
    rt = make_runtime("flashcards")
    _seed_cards(rt, "c1")

    rt.on_action("card.review", {"card_id": "c1", "rating": "good"})
    assert _schedule_for(rt, "c1")["interval"] == 1

    rt.on_action("card.review", {"card_id": "c1", "rating": "good"})
    assert _schedule_for(rt, "c1")["interval"] == 6

    rt.on_action("card.review", {"card_id": "c1", "rating": "good"})
    third = _schedule_for(rt, "c1")
    # Third "good" multiplies previous interval (6) by ease (≈2.5 after 2 goods).
    assert third["interval"] >= 14
    assert third["repetitions"] == 3


def test_sm2_again_resets() -> None:
    rt = make_runtime("flashcards")
    _seed_cards(rt, "c1")
    for _ in range(3):
        rt.on_action("card.review", {"card_id": "c1", "rating": "good"})
    rt.on_action("card.review", {"card_id": "c1", "rating": "again"})
    entry = _schedule_for(rt, "c1")
    assert entry["repetitions"] == 0
    assert entry["interval"] == 1


def test_binary_progression() -> None:
    rt = make_runtime("flashcards")
    _seed_cards(rt, "c1", rating_mode="binary")

    expected = [1, 3, 7, 14, 30]
    for want in expected:
        rt.on_action("card.review", {"card_id": "c1", "rating": "got"})
        assert _schedule_for(rt, "c1")["interval"] == want

    rt.on_action("card.review", {"card_id": "c1", "rating": "missed"})
    entry = _schedule_for(rt, "c1")
    assert entry["interval"] == 1
    assert entry["repetitions"] == 0


def test_schedule_isolated_per_user() -> None:
    field_store = MemoryKVStore()
    file_storage = MemoryFileStorage()

    def runtime_for(user_id: str, permission: Permission) -> ActivityRuntime:
        return ActivityRuntime(
            SAMPLES_DIR / "flashcards",
            field_store,
            file_storage,
            "a1",
            "c1",
            user_id,
            permission,
        )

    editor = runtime_for("author", Permission.edit)
    editor.on_action(
        "config.save",
        {"cards": [{"id": "c1", "front": "f", "back": "b"}], "rating_mode": "sm2"},
    )

    rt_alice = runtime_for("alice", Permission.play)
    rt_alice.on_action("card.review", {"card_id": "c1", "rating": "good"})
    alice_schedule: list[dict[str, Any]] = rt_alice.get_state()["schedule"]  # type: ignore[assignment]
    assert len(alice_schedule) == 1

    rt_bob = runtime_for("bob", Permission.play)
    bob_state = rt_bob.get_state()
    bob_cards: list[dict[str, Any]] = bob_state["cards"]  # type: ignore[assignment]
    assert bob_cards[0]["id"] == "c1"
    assert bob_state["schedule"] == []
