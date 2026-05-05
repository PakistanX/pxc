// Flashcards activity UI.
// edit  — author manages cards and rating model
// play  — student reviews due cards with self-rating
// view  — read-only flippable browse of all cards

export function setup(activity) {
  const element = activity.element;
  const permission = activity.permission;

  let cards = activity.state.cards || [];
  let ratingMode = activity.state.rating_mode || "sm2";
  let schedule = activity.state.schedule || [];
  const flipped = new Set();
  let currentCardId = null;

  function scheduleByCardId() {
    const m = new Map();
    for (const s of schedule) m.set(s.card_id, s);
    return m;
  }

  function dueCards() {
    const now = Date.now();
    const m = scheduleByCardId();
    return cards.filter((c) => {
      const s = m.get(c.id);
      return !s || s.due_at <= now;
    });
  }

  function pickNextDue() {
    const due = dueCards();
    if (due.length === 0) {
      currentCardId = null;
      return null;
    }
    if (currentCardId && due.some((c) => c.id === currentCardId)) {
      return due.find((c) => c.id === currentCardId);
    }
    currentCardId = due[0].id;
    return due[0];
  }

  function render() {
    element.innerHTML = `
      <style>
        #flashcards { font-family: sans-serif; max-width: 640px; }
        .row { display: flex; gap: 0.5rem; align-items: flex-start; margin: 0.5rem 0; }
        .row textarea { flex: 1; padding: 0.4rem; font-family: inherit; }
        button { padding: 0.4rem 0.8rem; cursor: pointer; }
        .danger { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .primary { background: #007bff; color: #fff; border: 0; }
        .muted { color: #666; font-style: italic; }
        .save-row { margin-top: 1rem; display: flex; gap: 0.5rem; align-items: center; }
        .feedback { padding: 0.5rem; border-radius: 4px; }
        .feedback.ok { background: #d4edda; color: #155724; }
        .feedback.err { background: #f8d7da; color: #721c24; }

        .card {
          perspective: 1000px;
          width: 100%; height: 220px;
          margin: 1rem 0;
          cursor: pointer;
        }
        .card-inner {
          position: relative; width: 100%; height: 100%;
          transition: transform 0.5s;
          transform-style: preserve-3d;
        }
        .card.flipped .card-inner { transform: rotateY(180deg); }
        .card-face {
          position: absolute; inset: 0;
          display: flex; align-items: center; justify-content: center;
          padding: 1rem; box-sizing: border-box;
          border: 1px solid #ccc; border-radius: 8px;
          background: #fff;
          backface-visibility: hidden;
          font-size: 1.1rem; text-align: center; white-space: pre-wrap;
        }
        .card-back { transform: rotateY(180deg); background: #f7f7ff; }

        .rate-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.5rem; }
        .rate-row button { flex: 1; min-width: 80px; }

        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1rem; }
        .grid .card { height: 160px; margin: 0; }

        .meta { font-size: 0.85rem; color: #666; margin-top: 0.5rem; }
      </style>
      <div id="flashcards"></div>
    `;
    const root = element.querySelector("#flashcards");
    if (permission === "edit") {
      renderEdit(root);
    } else if (permission === "play") {
      renderPlay(root);
    } else {
      renderView(root);
    }
  }

  function renderEdit(root) {
    const rowsHtml = cards
      .map(
        (c, i) => `
        <div class="row" data-index="${i}">
          <div style="flex:1">
            <textarea class="front" rows="3" placeholder="Front">${escapeHtml(c.front || "")}</textarea>
            <textarea class="back" rows="3" placeholder="Back" style="margin-top:0.25rem;">${escapeHtml(c.back || "")}</textarea>
          </div>
          <button type="button" class="danger remove">Remove</button>
        </div>`,
      )
      .join("");
    root.innerHTML = `
      <div>
        <strong>Rating model:</strong>
        <label style="margin-left:0.5rem;">
          <input type="radio" name="rating-mode" value="sm2" ${ratingMode === "sm2" ? "checked" : ""}>
          4-button SM-2
        </label>
        <label style="margin-left:0.5rem;">
          <input type="radio" name="rating-mode" value="binary" ${ratingMode === "binary" ? "checked" : ""}>
          Binary (got / missed)
        </label>
      </div>
      <div style="margin-top:1rem;">
        <strong>Cards:</strong>
        <div id="card-rows">${rowsHtml}</div>
        <button type="button" id="add-card" style="margin-top:0.5rem;">+ Add card</button>
      </div>
      <div class="save-row">
        <button type="button" class="primary" id="save">Save</button>
        <span id="save-feedback"></span>
      </div>
    `;
    root.querySelector("#add-card").addEventListener("click", () => {
      cards.push({ id: makeId(), front: "", back: "" });
      render();
    });
    root.querySelectorAll(".row").forEach((row) => {
      const i = parseInt(row.dataset.index, 10);
      row.querySelector(".front").addEventListener("input", (e) => {
        cards[i].front = e.target.value;
      });
      row.querySelector(".back").addEventListener("input", (e) => {
        cards[i].back = e.target.value;
      });
      row.querySelector(".remove").addEventListener("click", () => {
        cards.splice(i, 1);
        render();
      });
    });
    root.querySelectorAll('input[name="rating-mode"]').forEach((r) => {
      r.addEventListener("change", (e) => {
        if (e.target.checked) ratingMode = e.target.value;
      });
    });
    root.querySelector("#save").addEventListener("click", async () => {
      const fb = root.querySelector("#save-feedback");
      try {
        await activity.sendAction("config.save", {
          cards: cards.map((c) => ({
            id: c.id || makeId(),
            front: (c.front || "").trim(),
            back: (c.back || "").trim(),
          })).filter((c) => c.front || c.back),
          rating_mode: ratingMode,
        });
        fb.innerHTML = '<span class="feedback ok">Saved.</span>';
      } catch (err) {
        fb.innerHTML = `<span class="feedback err">${escapeHtml(err.message)}</span>`;
      }
    });
  }

  function renderPlay(root) {
    if (cards.length === 0) {
      root.innerHTML = `<p class="muted">No cards have been added yet.</p>`;
      return;
    }
    const card = pickNextDue();
    if (!card) {
      root.innerHTML = `
        <p class="muted">All caught up — no cards due right now.</p>
        <p class="meta">${cards.length} total card(s) in this deck.</p>`;
      return;
    }
    const isFlipped = flipped.has(card.id);
    const rateButtons = ratingMode === "binary"
      ? [
          { rating: "missed", label: "Missed" },
          { rating: "got", label: "Got it" },
        ]
      : [
          { rating: "again", label: "Again" },
          { rating: "hard", label: "Hard" },
          { rating: "good", label: "Good" },
          { rating: "easy", label: "Easy" },
        ];
    const rateHtml = isFlipped
      ? `<div class="rate-row">${rateButtons
          .map((b) => `<button type="button" data-rating="${b.rating}">${b.label}</button>`)
          .join("")}</div>`
      : `<p class="muted">Click the card to reveal the back.</p>`;
    const due = dueCards();
    root.innerHTML = `
      <p class="meta">${due.length} card(s) due of ${cards.length} total.</p>
      <div class="card ${isFlipped ? "flipped" : ""}" id="flip-card">
        <div class="card-inner">
          <div class="card-face card-front">${escapeHtml(card.front)}</div>
          <div class="card-face card-back">${escapeHtml(card.back)}</div>
        </div>
      </div>
      ${rateHtml}
    `;
    root.querySelector("#flip-card").addEventListener("click", () => {
      if (flipped.has(card.id)) flipped.delete(card.id);
      else flipped.add(card.id);
      render();
    });
    root.querySelectorAll(".rate-row button").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const rating = btn.dataset.rating;
        flipped.delete(card.id);
        currentCardId = null;
        try {
          await activity.sendAction("card.review", { card_id: card.id, rating });
        } catch (_) {
          // schedule update arrives via fields.change.schedule; ignore network errors here
        }
      });
    });
  }

  function renderView(root) {
    if (cards.length === 0) {
      root.innerHTML = `<p class="muted">No cards have been added yet.</p>`;
      return;
    }
    root.innerHTML = `
      <p class="meta">${cards.length} card(s). Click a card to flip.</p>
      <div class="grid">
        ${cards
          .map(
            (c) => `
          <div class="card ${flipped.has(c.id) ? "flipped" : ""}" data-id="${escapeHtml(c.id)}">
            <div class="card-inner">
              <div class="card-face card-front">${escapeHtml(c.front)}</div>
              <div class="card-face card-back">${escapeHtml(c.back)}</div>
            </div>
          </div>`,
          )
          .join("")}
      </div>
    `;
    root.querySelectorAll(".card").forEach((el) => {
      el.addEventListener("click", () => {
        const id = el.dataset.id;
        if (flipped.has(id)) flipped.delete(id);
        else flipped.add(id);
        render();
      });
    });
  }

  function makeId() {
    if (typeof crypto !== "undefined" && crypto.randomUUID) {
      return crypto.randomUUID();
    }
    return "c-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str == null ? "" : String(str);
    return div.innerHTML;
  }

  activity.onEvent = (name, value) => {
    if (name === "fields.change.cards") {
      cards = value || [];
      activity.state.cards = cards;
      render();
    } else if (name === "fields.change.rating_mode") {
      ratingMode = value || "sm2";
      activity.state.rating_mode = ratingMode;
      render();
    } else if (name === "fields.change.schedule") {
      schedule = value || [];
      activity.state.schedule = schedule;
      render();
    }
  };

  render();
}
