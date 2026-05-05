// Flashcards plugin — spaced-repetition flip cards.
//
// Actions handled:
// - config.save: replace cards and rating_mode (edit only)
// - card.review: update the calling user's schedule for a single card (play only)

import { getField, sendEvent, setField } from "pxc:sandbox/state";

const RATING_MODES = ["sm2", "binary"];
const DAY_MS = 86_400_000;
const BINARY_INTERVALS = [1, 3, 7, 14, 30];
const SM2_QUALITY = { again: 0, hard: 3, good: 4, easy: 5 };
const DEFAULT_EASE = 2.5;

export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  if (name === "config.save") {
    handleConfigSave(value, permission);
  } else if (name === "card.review") {
    handleCardReview(value, context, permission);
  }
  return "";
}

export function getState(context, permission) {
  const state = {
    cards: JSON.parse(getField("cards")),
    rating_mode: JSON.parse(getField("rating_mode")),
  };
  if (permission === "play") {
    state.schedule = JSON.parse(getField("schedule"));
  }
  return JSON.stringify(state);
}

function handleConfigSave(config, permission) {
  if (permission !== "edit") {
    console.log("config.save rejected: permission is " + permission);
    return;
  }
  const cards = Array.isArray(config.cards) ? config.cards : [];
  const ratingMode = RATING_MODES.includes(config.rating_mode)
    ? config.rating_mode
    : "sm2";
  setField("cards", JSON.stringify(cards));
  setField("rating_mode", JSON.stringify(ratingMode));
  sendEvent("fields.change.cards", JSON.stringify(cards), null, "play");
  sendEvent("fields.change.rating_mode", JSON.stringify(ratingMode), null, "play");
}

function handleCardReview(value, context, permission) {
  if (permission !== "play") {
    console.log("card.review rejected: permission is " + permission);
    return;
  }
  const cardId = value && typeof value.card_id === "string" ? value.card_id : "";
  const rating = value && typeof value.rating === "string" ? value.rating : "";
  if (!cardId || !rating) {
    return;
  }
  const ratingMode = JSON.parse(getField("rating_mode"));
  const schedule = JSON.parse(getField("schedule"));
  const idx = schedule.findIndex((s) => s.card_id === cardId);
  const prev = idx >= 0 ? schedule[idx] : newScheduleEntry(cardId);
  const next = ratingMode === "binary"
    ? applyBinary(prev, rating)
    : applySm2(prev, rating);
  if (idx >= 0) {
    schedule[idx] = next;
  } else {
    schedule.push(next);
  }
  setField("schedule", JSON.stringify(schedule));
  sendEvent(
    "fields.change.schedule",
    JSON.stringify(schedule),
    { userId: context.userId },
    "play",
  );
}

function newScheduleEntry(cardId) {
  return {
    card_id: cardId,
    due_at: 0,
    ease: DEFAULT_EASE,
    interval: 0,
    repetitions: 0,
  };
}

function applySm2(prev, rating) {
  const quality = rating in SM2_QUALITY ? SM2_QUALITY[rating] : SM2_QUALITY.good;
  let { ease, interval, repetitions } = prev;
  if (quality < 3) {
    repetitions = 0;
    interval = 1;
  } else {
    if (repetitions === 0) {
      interval = 1;
    } else if (repetitions === 1) {
      interval = 6;
    } else {
      interval = Math.round(interval * ease);
    }
    repetitions += 1;
  }
  ease = Math.max(
    1.3,
    ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
  );
  return {
    card_id: prev.card_id,
    due_at: Date.now() + interval * DAY_MS,
    ease,
    interval,
    repetitions,
  };
}

function applyBinary(prev, rating) {
  let { interval, repetitions } = prev;
  if (rating === "got") {
    const step = Math.min(repetitions, BINARY_INTERVALS.length - 1);
    interval = BINARY_INTERVALS[step];
    repetitions += 1;
  } else {
    interval = 1;
    repetitions = 0;
  }
  return {
    card_id: prev.card_id,
    due_at: Date.now() + interval * DAY_MS,
    ease: prev.ease,
    interval,
    repetitions,
  };
}
