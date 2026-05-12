"""Tests for the chess sample activity."""

import json
from typing import Any

from pxc.lib.permission import Permission
from pxc.lib.tests.samples.conftest import make_runtime

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

# Scholar's mate move sequence: 1.e4 e5 2.Bc4 Nc6 3.Qh5 Nf6?? 4.Qxf7#
SCHOLARS_MATE = [
    ("white", "e2", "e4"),
    ("black", "e7", "e5"),
    ("white", "f1", "c4"),
    ("black", "b8", "c6"),
    ("white", "d1", "h5"),
    ("black", "g8", "f6"),
    ("white", "h5", "f7"),
]


def _setup_game(
    white: str = "alice", black: str = "bob"
) -> "pxc.lib.runtime.ActivityRuntime":  # type: ignore[name-defined]
    """Create a runtime with two players joined and ready to play."""
    rt = make_runtime("chess", user_id=white)
    rt.on_action("game.join", {})
    rt.user_id = black
    rt.on_action("game.join", {})
    rt.clear_pending_events()
    return rt


def _play_scholars_mate(
    rt: "pxc.lib.runtime.ActivityRuntime",  # type: ignore[name-defined]
) -> None:
    """Play the scholar's mate sequence on the given runtime."""
    for user, from_sq, to_sq in SCHOLARS_MATE:
        rt.user_id = user
        rt.on_action("game.move", {"from": from_sq, "to": to_sq})


def test_get_state_defaults() -> None:
    rt = make_runtime("chess")
    state = rt.get_state()
    assert state["fen"] == START_FEN
    assert state["white"] == ""
    assert state["black"] == ""
    assert state["status"] == "waiting"
    assert state["result"] == ""
    assert state["records"] == []


def test_join_assigns_white_then_black() -> None:
    rt = make_runtime("chess", user_id="alice")
    rt.on_action("game.join", {})
    state = rt.get_state()
    assert state["white"] == "alice"
    assert state["black"] == ""
    assert state["status"] == "waiting"

    rt.user_id = "bob"
    rt.on_action("game.join", {})
    state = rt.get_state()
    assert state["white"] == "alice"
    assert state["black"] == "bob"
    assert state["status"] == "playing"


def test_join_emits_event() -> None:
    rt = make_runtime("chess", user_id="alice")
    rt.on_action("game.join", {})
    events = rt.clear_pending_events()
    updated = [e for e in events if e["name"] == "game.updated"]
    assert len(updated) == 1
    value = json.loads(updated[0]["value"])
    assert value["white"] == "alice"


def test_same_user_cannot_join_twice() -> None:
    rt = make_runtime("chess", user_id="alice")
    rt.on_action("game.join", {})
    rt.on_action("game.join", {})
    state = rt.get_state()
    assert state["white"] == "alice"
    assert state["black"] == ""


def test_join_ignored_when_playing() -> None:
    rt = _setup_game()
    rt.user_id = "charlie"
    rt.on_action("game.join", {})
    state = rt.get_state()
    assert state["white"] == "alice"
    assert state["black"] == "bob"


def test_valid_move() -> None:
    rt = _setup_game()
    rt.user_id = "alice"
    rt.on_action("game.move", {"from": "e2", "to": "e4"})
    state = rt.get_state()
    assert state["status"] == "playing"
    assert state["fen"] != START_FEN
    # Black's turn now
    assert " b " in state["fen"]


def test_wrong_turn_rejected() -> None:
    rt = _setup_game()
    rt.user_id = "bob"
    rt.on_action("game.move", {"from": "e7", "to": "e5"})
    state = rt.get_state()
    assert state["fen"] == START_FEN


def test_illegal_move_rejected() -> None:
    rt = _setup_game()
    rt.user_id = "alice"
    rt.on_action("game.move", {"from": "e2", "to": "e5"})
    state = rt.get_state()
    assert state["fen"] == START_FEN


def test_move_emits_event() -> None:
    rt = _setup_game()
    rt.user_id = "alice"
    rt.on_action("game.move", {"from": "e2", "to": "e4"})
    events = rt.clear_pending_events()
    updated = [e for e in events if e["name"] == "game.updated"]
    assert len(updated) == 1
    value = json.loads(updated[0]["value"])
    assert value["fen"] != START_FEN


def test_spectator_cannot_move() -> None:
    rt = _setup_game()
    rt.user_id = "charlie"
    rt.on_action("game.move", {"from": "e2", "to": "e4"})
    state = rt.get_state()
    assert state["fen"] == START_FEN


def test_checkmate_ends_game() -> None:
    rt = _setup_game(white="white", black="black")
    _play_scholars_mate(rt)
    state = rt.get_state()
    assert state["status"] == "ended"
    assert state["result"] == "white"
    records: list[Any] = state["records"]
    assert len(records) == 1
    assert records[0]["value"]["winner"] == "white"
    assert records[0]["value"]["result"] == "checkmate"


def test_checkmate_emits_records_changed() -> None:
    rt = _setup_game(white="white", black="black")
    _play_scholars_mate(rt)
    events = rt.clear_pending_events()
    records_events = [e for e in events if e["name"] == "records.changed"]
    assert len(records_events) == 1


def test_reset_after_game_ends() -> None:
    rt = _setup_game(white="white", black="black")
    _play_scholars_mate(rt)
    rt.clear_pending_events()

    rt.on_action("game.reset", {})
    state = rt.get_state()
    assert state["status"] == "waiting"
    assert state["white"] == ""
    assert state["black"] == ""
    assert state["fen"] == START_FEN
    # Records are preserved
    assert len(state["records"]) == 1


def test_reset_ignored_during_play() -> None:
    rt = _setup_game()
    rt.user_id = "alice"
    rt.on_action("game.reset", {})
    state = rt.get_state()
    assert state["status"] == "playing"


def test_records_delete_requires_edit() -> None:
    rt = _setup_game(white="white", black="black")
    _play_scholars_mate(rt)
    state = rt.get_state()
    record_id: int = state["records"][0]["id"]

    # Play mode cannot delete
    rt.on_action("records.delete", record_id)
    assert len(rt.get_state()["records"]) == 1

    # Edit mode can delete
    rt.permission = Permission.edit
    rt.on_action("records.delete", record_id)
    assert len(rt.get_state()["records"]) == 0


def test_records_delete_emits_event() -> None:
    rt = _setup_game(white="white", black="black")
    _play_scholars_mate(rt)
    rt.clear_pending_events()

    rt.permission = Permission.edit
    record_id: int = rt.get_state()["records"][0]["id"]
    rt.on_action("records.delete", record_id)
    events = rt.clear_pending_events()
    records_events = [e for e in events if e["name"] == "records.changed"]
    assert len(records_events) == 1
    updated = json.loads(records_events[0]["value"])
    assert len(updated["records"]) == 0


def test_player_remove_single_white() -> None:
    rt = make_runtime("chess", permission=Permission.edit, user_id="alice")
    rt.on_action("game.join", {})
    rt.clear_pending_events()

    state = rt.get_state()
    assert state["white"] == "alice"
    assert state["black"] == ""

    rt.on_action("player.remove", "alice")
    state = rt.get_state()
    assert state["white"] == ""
    assert state["black"] == ""
    assert state["status"] == "waiting"


def test_player_remove_single_black() -> None:
    rt = make_runtime("chess", permission=Permission.edit)
    rt.user_id = "alice"
    rt.on_action("game.join", {})
    rt.user_id = "bob"
    rt.on_action("game.join", {})
    rt.clear_pending_events()

    state = rt.get_state()
    assert state["status"] == "playing"

    # Set back to edit mode before attempting remove
    rt.permission = Permission.edit
    rt.on_action("player.remove", "bob")
    state = rt.get_state()
    # Remove only works when exactly one player joined
    assert state["black"] == "bob"


def test_player_remove_requires_edit() -> None:
    rt = make_runtime("chess", user_id="alice")
    rt.on_action("game.join", {})
    rt.clear_pending_events()

    # Play mode cannot remove
    rt.on_action("player.remove", "alice")
    state = rt.get_state()
    assert state["white"] == "alice"


def test_player_remove_requires_single_player() -> None:
    rt = make_runtime("chess", permission=Permission.edit)
    rt.user_id = "alice"
    rt.on_action("game.join", {})
    rt.user_id = "bob"
    rt.on_action("game.join", {})
    rt.clear_pending_events()

    # Both players joined, remove should be ignored
    rt.on_action("player.remove", "alice")
    state = rt.get_state()
    assert state["white"] == "alice"
    assert state["black"] == "bob"


def test_player_remove_emits_event() -> None:
    rt = make_runtime("chess", permission=Permission.edit, user_id="alice")
    rt.on_action("game.join", {})
    rt.clear_pending_events()

    rt.on_action("player.remove", "alice")
    events = rt.clear_pending_events()
    updated = [e for e in events if e["name"] == "game.updated"]
    assert len(updated) == 1
    value = json.loads(updated[0]["value"])
    assert value["white"] == ""


def test_game_stop_during_play() -> None:
    rt = _setup_game()
    rt.user_id = "alice"
    rt.on_action("game.move", {"from": "e2", "to": "e4"})
    rt.clear_pending_events()

    rt.permission = Permission.edit
    rt.on_action("game.stop", {})
    state = rt.get_state()
    assert state["status"] == "waiting"
    assert state["white"] == ""
    assert state["black"] == ""
    assert state["fen"] == START_FEN
    assert state["result"] == ""


def test_game_stop_requires_edit() -> None:
    rt = _setup_game()
    rt.user_id = "alice"
    rt.on_action("game.move", {"from": "e2", "to": "e4"})
    rt.clear_pending_events()

    # Play mode cannot stop
    rt.on_action("game.stop", {})
    state = rt.get_state()
    assert state["status"] == "playing"


def test_game_stop_requires_playing() -> None:
    rt = make_runtime("chess", permission=Permission.edit)
    rt.user_id = "alice"
    rt.on_action("game.join", {})
    rt.clear_pending_events()

    # Only one player, game is waiting
    rt.on_action("game.stop", {})
    state = rt.get_state()
    assert state["status"] == "waiting"
    assert state["white"] == "alice"


def test_game_stop_emits_event() -> None:
    rt = _setup_game()
    rt.user_id = "alice"
    rt.on_action("game.move", {"from": "e2", "to": "e4"})
    rt.clear_pending_events()

    rt.permission = Permission.edit
    rt.on_action("game.stop", {})
    events = rt.clear_pending_events()
    updated = [e for e in events if e["name"] == "game.updated"]
    assert len(updated) == 1
    value = json.loads(updated[0]["value"])
    assert value["status"] == "waiting"
    assert value["white"] == ""
    assert value["black"] == ""
