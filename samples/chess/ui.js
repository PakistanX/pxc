// Two-player chess UI.
//
// Renders an 8x8 board with Unicode pieces, click-to-select / click-to-move
// interaction, player info, game status, and a records panel.

import { Chess } from "chess.js";

const PIECE_CHARS = {
  wp: "\u2659", wn: "\u2658", wb: "\u2657", wr: "\u2656", wq: "\u2655", wk: "\u2654",
  bp: "\u265F", bn: "\u265E", bb: "\u265D", br: "\u265C", bq: "\u265B", bk: "\u265A",
};

const PROMO_PIECES = ["q", "r", "b", "n"];

export function setup(activity) {
  const el = activity.element;
  const userId = activity.context.user_id;
  const canAct = activity.permission !== "view";
  const isEditor = activity.permission === "edit";

  let { fen, white, black, status, result, records, discord_webhook_url } = activity.state;
  let selected = null; // selected square like "e2"
  let legalMoves = []; // [{from, to, promotion}, ...]
  let pendingPromotion = null; // {from, to} when awaiting promo choice
  let webhookError = null; // error message from webhook.error event

  function myColor() {
    if (white === userId) return "w";
    if (black === userId) return "b";
    return null;
  }

  function isMyTurn() {
    if (status !== "playing") return false;
    const color = myColor();
    if (!color) return false;
    const chess = new Chess(fen);
    return chess.turn() === color;
  }

  function canInteract() {
    return canAct && isMyTurn();
  }

  function parseFen(fenStr) {
    const board = [];
    const rows = fenStr.split(" ")[0].split("/");
    for (const row of rows) {
      const rank = [];
      for (const ch of row) {
        if (ch >= "1" && ch <= "8") {
          for (let i = 0; i < parseInt(ch); i++) rank.push(null);
        } else {
          const color = ch === ch.toUpperCase() ? "w" : "b";
          const piece = ch.toLowerCase();
          rank.push(color + piece);
        }
      }
      board.push(rank);
    }
    return board;
  }

  function squareToCoord(sq, flipped) {
    const file = sq.charCodeAt(0) - 97;
    const rank = parseInt(sq[1]) - 1;
    const row = flipped ? rank : 7 - rank;
    const col = flipped ? 7 - file : file;
    return { row, col };
  }

  function coordToSquare(row, col, flipped) {
    const file = flipped ? 7 - col : col;
    const rank = flipped ? row : 7 - row;
    return String.fromCharCode(97 + file) + (rank + 1);
  }

  function render() {
    const flipped = myColor() === "b";
    const board = parseFen(fen);
    const chess = new Chess(fen);
    const turn = chess.turn();
    const turnLabel = turn === "w" ? "White" : "Black";
    const inCheck = chess.inCheck();

    const legalDests = new Set(legalMoves.map((m) => m.to));

    let statusHtml = "";
    if (status === "waiting") {
      const joined = (white ? 1 : 0) + (black ? 1 : 0);
      if (canAct && !myColor()) {
        statusHtml = `<div class="cs-status">
          <span>${joined}/2 players joined</span>
          <button class="cs-btn" id="cs-join">Join game</button>
        </div>`;
      } else if (myColor()) {
        statusHtml = `<div class="cs-status">Waiting for opponent... (${joined}/2)</div>`;
      } else {
        statusHtml = `<div class="cs-status">Waiting for players... (${joined}/2)</div>`;
      }
    } else if (status === "playing") {
      const turnUser = turn === "w" ? white : black;
      const msg = turnUser === userId
        ? `<strong>Your turn</strong>${inCheck ? " (check!)" : ""}`
        : `${escapeHtml(turnUser)}'s turn${inCheck ? " (check!)" : ""}`;
      statusHtml = `<div class="cs-status">${msg}`;
      if (isEditor) {
        statusHtml += `<button class="cs-btn" id="cs-stop" style="margin-left: 8px;">Stop game</button>`;
      }
      statusHtml += `</div>`;
    } else if (status === "ended") {
      let msg = "";
      if (result === "draw") {
        msg = "Game over: draw";
      } else {
        const winnerUser = result === "white" ? white : black;
        msg = `Checkmate! ${escapeHtml(winnerUser)} wins`;
      }
      statusHtml = `<div class="cs-status">${msg}</div>`;
      if (canAct) {
        statusHtml += `<button class="cs-btn" id="cs-reset">New game</button>`;
      }
    }

    let playersHtml = `
      <div class="cs-players">
        <div class="cs-player ${turn === "w" && status === "playing" ? "cs-active" : ""}">
          <span class="cs-dot cs-white-dot"></span> ${white ? escapeHtml(white) : "(empty)"}
          ${isEditor && status === "waiting" && white && !black ? `<button class="cs-player-remove" data-player="white">remove</button>` : ""}
        </div>
        <div class="cs-player ${turn === "b" && status === "playing" ? "cs-active" : ""}">
          <span class="cs-dot cs-black-dot"></span> ${black ? escapeHtml(black) : "(empty)"}
          ${isEditor && status === "waiting" && black && !white ? `<button class="cs-player-remove" data-player="black">remove</button>` : ""}
        </div>
      </div>`;

    let configHtml = "";
    if (isEditor) {
      const errorMsg = webhookError ? `<div class="cs-error-banner">${escapeHtml(webhookError)} <button class="cs-error-close" id="cs-error-close">×</button></div>` : "";
      configHtml = `
        <div class="cs-config">
          <h4>Discord Webhook</h4>
          ${errorMsg}
          <input type="text" id="cs-webhook-url" placeholder="Discord webhook URL" value="${escapeHtml(discord_webhook_url || "")}" class="cs-config-input" />
          <button class="cs-btn" id="cs-save-config">Save</button>
        </div>`;
    }

    let recordsHtml = "";
    if (records.length > 0) {
      const rows = records.map((r) => {
        const v = r.value;
        const res = v.winner ? `${escapeHtml(v.winner)} (${v.result})` : v.result;
        const del = isEditor
          ? `<button class="cs-del" data-id="${r.id}">x</button>` : "";
        return `<tr>
          <td>${escapeHtml(v.white)}</td><td>${escapeHtml(v.black)}</td>
          <td>${res}</td><td>${del}</td>
        </tr>`;
      }).join("");
      recordsHtml = `
        <div class="cs-records">
          <h4>Records</h4>
          <table><thead><tr><th>White</th><th>Black</th><th>Result</th><th></th></tr></thead>
          <tbody>${rows}</tbody></table>
        </div>`;
    }

    let promoHtml = "";
    if (pendingPromotion) {
      const color = myColor();
      const pieces = PROMO_PIECES.map((p) => {
        const key = color + p;
        return `<button class="cs-promo-btn" data-piece="${p}">${PIECE_CHARS[key]}</button>`;
      }).join("");
      promoHtml = `<div class="cs-promo-overlay"><div class="cs-promo-picker">${pieces}</div></div>`;
    }

    // Build board squares
    let squaresHtml = "";
    for (let row = 0; row < 8; row++) {
      for (let col = 0; col < 8; col++) {
        const sq = coordToSquare(row, col, flipped);
        const boardRow = flipped ? 7 - row : row;
        const boardCol = flipped ? 7 - col : col;
        const piece = board[boardRow][boardCol];
        const isLight = (boardRow + boardCol) % 2 === 1;
        const cls = ["cs-sq"];
        cls.push(isLight ? "cs-light" : "cs-dark");
        if (selected === sq) cls.push("cs-selected");
        if (legalDests.has(sq)) cls.push(piece ? "cs-capture" : "cs-legal");
        const pieceChar = piece ? PIECE_CHARS[piece] : "";
        squaresHtml += `<div class="${cls.join(" ")}" data-sq="${sq}">${pieceChar}</div>`;
      }
    }

    // File/rank labels
    const files = flipped ? "hgfedcba" : "abcdefgh";
    const ranks = flipped ? "12345678" : "87654321";
    let fileLabelHtml = "";
    for (const f of files) {
      fileLabelHtml += `<span class="cs-file-label">${f}</span>`;
    }
    let rankLabelHtml = "";
    for (const r of ranks) {
      rankLabelHtml += `<span class="cs-rank-label">${r}</span>`;
    }

    el.innerHTML = `
      <style>
        .cs-wrap { display: flex; gap: 20px; font-family: system-ui, sans-serif; align-items: flex-start; }
        .cs-board-area { position: relative; }
        .cs-board { display: grid; grid-template-columns: repeat(8, 60px); grid-template-rows: repeat(8, 60px); border: 2px solid #333; }
        .cs-sq { display: flex; align-items: center; justify-content: center; font-size: 40px; cursor: default; position: relative; user-select: none; }
        .cs-light { background: #f0d9b5; }
        .cs-dark { background: #b58863; }
        .cs-selected { background: #ffff66 !important; }
        .cs-legal::after { content: ""; position: absolute; width: 18px; height: 18px; border-radius: 50%; background: rgba(0,0,0,0.2); }
        .cs-capture { box-shadow: inset 0 0 0 4px rgba(0,0,0,0.3); }
        .cs-file-labels { display: grid; grid-template-columns: repeat(8, 60px); text-align: center; font-size: 12px; color: #666; }
        .cs-rank-labels { display: flex; flex-direction: column; justify-content: space-around; font-size: 12px; color: #666; padding-right: 4px; height: 480px; text-align: center; }
        .cs-board-row { display: flex; }
        .cs-panel { min-width: 200px; max-width: 280px; }
        .cs-status { margin-bottom: 12px; padding: 8px; background: #f5f5f5; border-radius: 4px; }
        .cs-btn { display: inline-block; margin-top: 8px; padding: 6px 16px; background: #4a90d9; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
        .cs-btn:hover { background: #357abd; }
        .cs-players { margin-bottom: 12px; }
        .cs-player { padding: 4px 0; display: flex; align-items: center; gap: 6px; }
        .cs-active { font-weight: bold; }
        .cs-dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 1px solid #999; }
        .cs-white-dot { background: #fff; }
        .cs-black-dot { background: #333; }
        .cs-player-remove { background: none; border: none; color: #c00; cursor: pointer; font-size: 12px; padding: 0 4px; margin-left: auto; text-decoration: underline; }
        .cs-player-remove:hover { font-weight: bold; }
        .cs-records h4 { margin: 12px 0 6px; }
        .cs-records table { border-collapse: collapse; font-size: 13px; width: 100%; }
        .cs-records th, .cs-records td { padding: 3px 6px; border: 1px solid #ddd; text-align: left; }
        .cs-records th { background: #f0f0f0; }
        .cs-del { background: none; border: none; color: #c00; cursor: pointer; font-weight: bold; padding: 0 4px; }
        .cs-promo-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 10; }
        .cs-promo-picker { display: flex; gap: 8px; background: #fff; padding: 16px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .cs-promo-btn { font-size: 40px; background: none; border: 2px solid #ccc; border-radius: 4px; padding: 8px; cursor: pointer; }
        .cs-promo-btn:hover { border-color: #4a90d9; background: #e8f0fe; }
        .cs-config { margin-bottom: 12px; padding: 8px; background: #f5f5f5; border-radius: 4px; }
        .cs-config h4 { margin: 0 0 8px 0; }
        .cs-config-input { width: 100%; padding: 6px; margin-bottom: 8px; border: 1px solid #ccc; border-radius: 4px; font-size: 13px; box-sizing: border-box; }
        .cs-error-banner { background: #ffebee; border: 1px solid #f44336; color: #c62828; padding: 8px; border-radius: 4px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
        .cs-error-close { background: none; border: none; color: #c62828; cursor: pointer; font-size: 18px; padding: 0; }
      </style>
      <div class="cs-wrap">
        <div class="cs-board-area">
          <div class="cs-board-row">
            <div class="cs-rank-labels">${rankLabelHtml}</div>
            <div>
              <div class="cs-board" id="cs-board">${squaresHtml}</div>
              <div class="cs-file-labels">${fileLabelHtml}</div>
            </div>
          </div>
          ${promoHtml}
        </div>
        <div class="cs-panel">
          ${configHtml}
          ${playersHtml}
          ${statusHtml}
          ${recordsHtml}
        </div>
      </div>
    `;

    bindEvents();
  }

  function bindEvents() {
    const saveConfigBtn = el.querySelector("#cs-save-config");
    if (saveConfigBtn) {
      saveConfigBtn.addEventListener("click", () => {
        const url = el.querySelector("#cs-webhook-url").value;
        activity.sendAction("config.save", { discord_webhook_url: url });
      });
    }

    const errorClose = el.querySelector("#cs-error-close");
    if (errorClose) {
      errorClose.addEventListener("click", () => {
        webhookError = null;
        render();
      });
    }

    const joinBtn = el.querySelector("#cs-join");
    if (joinBtn) {
      joinBtn.addEventListener("click", () => activity.sendAction("game.join", {}));
    }

    const resetBtn = el.querySelector("#cs-reset");
    if (resetBtn) {
      resetBtn.addEventListener("click", () => activity.sendAction("game.reset", {}));
    }

    const stopBtn = el.querySelector("#cs-stop");
    if (stopBtn) {
      stopBtn.addEventListener("click", () => activity.sendAction("game.stop", {}));
    }

    el.querySelectorAll(".cs-player-remove").forEach((btn) => {
      btn.addEventListener("click", () => {
        const player = btn.dataset.player;
        activity.sendAction("player.remove", player === "white" ? white : black);
      });
    });

    el.querySelectorAll(".cs-del").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = parseInt(btn.dataset.id);
        activity.sendAction("records.delete", id);
      });
    });

    if (pendingPromotion) {
      el.querySelectorAll(".cs-promo-btn").forEach((btn) => {
        btn.addEventListener("click", () => {
          const promotion = btn.dataset.piece;
          activity.sendAction("game.move", {
            from: pendingPromotion.from,
            to: pendingPromotion.to,
            promotion,
          });
          pendingPromotion = null;
          selected = null;
          legalMoves = [];
          render();
        });
      });
    }

    if (canInteract()) {
      el.querySelectorAll(".cs-sq").forEach((sqEl) => {
        sqEl.style.cursor = "pointer";
        sqEl.addEventListener("click", () => handleSquareClick(sqEl.dataset.sq));
      });
    }
  }

  function handleSquareClick(sq) {
    if (pendingPromotion) return;

    // If clicking a legal destination, make the move
    const moveMatch = legalMoves.find((m) => m.to === sq);
    if (selected && moveMatch) {
      // Check for promotion
      const chess = new Chess(fen);
      const promoMoves = legalMoves.filter((m) => m.to === sq && m.promotion);
      if (promoMoves.length > 0) {
        pendingPromotion = { from: selected, to: sq };
        render();
        return;
      }
      activity.sendAction("game.move", { from: selected, to: sq });
      selected = null;
      legalMoves = [];
      return;
    }

    // Select a piece
    const chess = new Chess(fen);
    const piece = chess.get(sq);
    if (piece && piece.color === myColor()) {
      selected = sq;
      legalMoves = chess.moves({ square: sq, verbose: true });
      render();
    } else {
      selected = null;
      legalMoves = [];
      render();
    }
  }

  activity.onEvent = (name, value) => {
    if (name === "game.updated") {
      fen = value.fen;
      white = value.white;
      black = value.black;
      status = value.status;
      result = value.result;
      selected = null;
      legalMoves = [];
      pendingPromotion = null;
      render();
    }
    if (name === "records.changed") {
      records = value;
      render();
    }
    if (name === "webhook.error") {
      webhookError = value;
      render();
    }
  };

  render();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
