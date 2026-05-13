// Multiplayer Flappy Bird sandbox.
//
// Actions:
// - game.position: relay the caller's bird position to all players.
// - game.over: persist best_score (per user) and update the course top-10.

import { getField, getUsernames, setField, sendEvent } from "pxc:sandbox/state";

function enrichTopScores(top) {
  const ids = [...new Set(top.map((s) => s.user).filter((x) => x))];
  const names = Object.fromEntries(getUsernames(ids));
  return top.map((s) => ({ ...s, username: names[s.user] || s.user }));
}

export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  const userId = context.userId || "anonymous";

  if (name === "game.position") {
    const names = Object.fromEntries(getUsernames([userId]));
    const payload = {
      user: userId,
      username: names[userId] || userId,
      x: Number(value.x) || 0,
      y: Number(value.y) || 0,
      scrollX: Number(value.scrollX) || 0,
      alive: Boolean(value.alive),
    };
    sendEvent("player.position", JSON.stringify(payload), null, "play");
    return "";
  }

  if (name === "scores.delete") {
    if (permission !== "edit") return "";
    const index = value;
    const top = JSON.parse(getField("top_scores"));
    if (index >= 0 && index < top.length) {
      top.splice(index, 1);
      setField("top_scores", JSON.stringify(top));
      sendEvent(
        "fields.change.top_scores",
        JSON.stringify(enrichTopScores(top)),
        null,
        "play",
      );
    }
    return "";
  }

  if (name === "game.over") {
    const score = Math.max(0, Math.floor(Number(value.score) || 0));

    const best = JSON.parse(getField("best_score"));
    if (score > best) {
      setField("best_score", JSON.stringify(score));
      sendEvent(
        "fields.change.best_score",
        JSON.stringify(score),
        { userId },
        "play",
      );
    }

    const top = JSON.parse(getField("top_scores"));
    top.push({ user: userId, score });
    top.sort((a, b) => b.score - a.score);
    const trimmed = top.slice(0, 10);
    setField("top_scores", JSON.stringify(trimmed));
    sendEvent(
      "fields.change.top_scores",
      JSON.stringify(enrichTopScores(trimmed)),
      null,
      "play",
    );
    return "";
  }

  return "";
}

export function getState(context, permission) {
  return JSON.stringify({
    best_score: JSON.parse(getField("best_score")),
    top_scores: enrichTopScores(JSON.parse(getField("top_scores"))),
  });
}
