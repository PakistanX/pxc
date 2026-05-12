// Two-player chess sandbox.
//
// Actions:
// - game.join: assign caller to the first available color slot
// - game.move: validate and apply a chess move
// - game.reset: reset the board after a game ends
// - records.delete: remove a game record (edit mode only)

import {
  getField,
  setField,
  sendEvent,
  logAppend,
  logGetRange,
  logDelete,
  getUsernames,
} from "pxc:sandbox/state";
import { httpRequest } from "pxc:sandbox/http";
import { Chess } from "chess.js";

const START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";

function resolveNames(ids) {
  const unique = [...new Set(ids.filter((x) => x))];
  return Object.fromEntries(getUsernames(unique));
}

// Convert a {id: name} map into the [{id, name}, ...] shape used in events
// (the schema builder forbids freeform-keyed objects).
function namesToList(map) {
  return Object.entries(map).map(([id, name]) => ({ id, name }));
}

function collectRecordIds(records) {
  const ids = [];
  for (const r of records) {
    ids.push(r.value.white, r.value.black);
    if (r.value.winner) ids.push(r.value.winner);
  }
  return ids;
}

function broadcastGameState() {
  const white = JSON.parse(getField("white"));
  const black = JSON.parse(getField("black"));
  const state = {
    fen: JSON.parse(getField("fen")),
    white,
    black,
    status: JSON.parse(getField("status")),
    result: JSON.parse(getField("result")),
    usernames: namesToList(resolveNames([white, black])),
  };
  sendEvent("game.updated", JSON.stringify(state), null, "view");
}

function broadcastRecords() {
  const records = JSON.parse(logGetRange("records", 0, 1000));
  sendEvent(
    "records.changed",
    JSON.stringify({
      records,
      usernames: namesToList(resolveNames(collectRecordIds(records))),
    }),
    null,
    "view",
  );
}

function postToDiscord(message) {
  const url = JSON.parse(getField("discord_webhook_url"));
  if (!url) return;

  const body = JSON.stringify({ content: message });
  const headers = JSON.stringify([
    ["Content-Type", "application/json"],
    ["User-Agent", "Application"],
  ]);

  try {
    const response = JSON.parse(httpRequest(url, "POST", body, headers));
    if (response.status < 200 || response.status >= 300) {
      sendEvent("webhook.error", JSON.stringify(`Discord webhook failed: ${response.status}`), null, "edit");
    }
  } catch (e) {
    sendEvent("webhook.error", JSON.stringify(`Discord webhook error: ${e}`), null, "edit");
  }
}

export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  const userId = context.userId || "anonymous";

  if (name === "config.save") {
    if (permission !== "edit") return "";
    setField("discord_webhook_url", JSON.stringify(value.discord_webhook_url));
    return "";
  }

  if (name === "game.join") {
    const status = JSON.parse(getField("status"));
    if (status !== "waiting") return "";

    const white = JSON.parse(getField("white"));
    const black = JSON.parse(getField("black"));
    if (white === userId || black === userId) return "";

    const joinerName = resolveNames([userId])[userId] || userId;
    if (!white) {
      setField("white", JSON.stringify(userId));
      postToDiscord(`♟️ Player \`${joinerName}\` joined the chess game and is looking for a contender!`);
    } else if (!black) {
      setField("black", JSON.stringify(userId));
      setField("status", JSON.stringify("playing"));
      const whiteName = resolveNames([white])[white] || white;
      postToDiscord(`⚔️ Player \`${joinerName}\` joined! The chess game between \`${whiteName}\` and \`${joinerName}\` is starting!`);
    }
    broadcastGameState();
    return "";
  }

  if (name === "game.move") {
    const status = JSON.parse(getField("status"));
    if (status !== "playing") return "";

    const fen = JSON.parse(getField("fen"));
    const white = JSON.parse(getField("white"));
    const black = JSON.parse(getField("black"));

    const chess = new Chess(fen);
    const turn = chess.turn();
    if ((turn === "w" && userId !== white) || (turn === "b" && userId !== black))
      return "";

    const move = chess.move({ from: value.from, to: value.to, promotion: value.promotion });
    if (!move) return "";

    setField("fen", JSON.stringify(chess.fen()));

    if (chess.isCheckmate()) {
      const winner = turn === "w" ? "white" : "black";
      setField("status", JSON.stringify("ended"));
      setField("result", JSON.stringify(winner));
      logAppend(
        "records",
        JSON.stringify({ white, black, result: "checkmate", winner }),
      );
      broadcastRecords();
    } else if (chess.isStalemate() || chess.isDraw()) {
      setField("status", JSON.stringify("ended"));
      setField("result", JSON.stringify("draw"));
      logAppend(
        "records",
        JSON.stringify({ white, black, result: "draw", winner: "" }),
      );
      broadcastRecords();
    }

    broadcastGameState();
    return "";
  }

  if (name === "game.reset") {
    const status = JSON.parse(getField("status"));
    if (status !== "ended") return "";

    setField("fen", JSON.stringify(START_FEN));
    setField("white", JSON.stringify(""));
    setField("black", JSON.stringify(""));
    setField("status", JSON.stringify("waiting"));
    setField("result", JSON.stringify(""));
    broadcastGameState();
    return "";
  }

  if (name === "player.remove") {
    if (permission !== "edit") return "";
    const status = JSON.parse(getField("status"));
    if (status !== "waiting") return "";

    const white = JSON.parse(getField("white"));
    const black = JSON.parse(getField("black"));
    const joined = (white ? 1 : 0) + (black ? 1 : 0);
    if (joined !== 1) return "";

    if (value === white) {
      setField("white", JSON.stringify(""));
    } else if (value === black) {
      setField("black", JSON.stringify(""));
    }
    broadcastGameState();
    return "";
  }

  if (name === "game.stop") {
    if (permission !== "edit") return "";
    const status = JSON.parse(getField("status"));
    if (status !== "playing") return "";

    setField("fen", JSON.stringify(START_FEN));
    setField("white", JSON.stringify(""));
    setField("black", JSON.stringify(""));
    setField("status", JSON.stringify("waiting"));
    setField("result", JSON.stringify(""));
    broadcastGameState();
    return "";
  }

  if (name === "records.delete") {
    if (permission !== "edit") return "";
    logDelete("records", value);
    broadcastRecords();
    return "";
  }

  return "";
}

export function getState(context, permission) {
  const white = JSON.parse(getField("white"));
  const black = JSON.parse(getField("black"));
  const records = JSON.parse(logGetRange("records", 0, 1000));
  const ids = [white, black, ...collectRecordIds(records)];
  return JSON.stringify({
    fen: JSON.parse(getField("fen")),
    white,
    black,
    status: JSON.parse(getField("status")),
    result: JSON.parse(getField("result")),
    records,
    usernames: namesToList(resolveNames(ids)),
  });
}
