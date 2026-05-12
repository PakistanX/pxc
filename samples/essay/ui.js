import { marked } from "marked";

const CSS = `
  .essay-wrap { font-family: system-ui, sans-serif; max-width: 800px; padding: 1rem; line-height: 1.5; }
  .essay-instructions { margin-bottom: 1.5rem; padding: 1rem; background: #f5f7fa; border-left: 4px solid #4a90d9; border-radius: 4px; }
  .essay-instructions :first-child { margin-top: 0; }
  .essay-instructions :last-child { margin-bottom: 0; }
  .essay-section { margin-bottom: 2rem; }
  .essay-section h3 { margin-bottom: 0.75rem; }
  .essay-textarea { width: 100%; min-height: 150px; padding: 0.5rem; font-family: inherit; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; resize: vertical; }
  .essay-label { display: block; margin: 0.5rem 0 0.25rem; font-weight: 600; font-size: 14px; }
  .essay-actions { display: flex; gap: 0.5rem; align-items: center; margin-top: 0.5rem; }
  .essay-btn { padding: 0.5rem 1.25rem; border: none; border-radius: 4px; cursor: pointer; font-size: 14px; }
  .essay-btn-primary { background: #4a90d9; color: #fff; }
  .essay-btn-primary:hover { background: #357abd; }
  .essay-btn-secondary { background: #e0e0e0; color: #333; }
  .essay-btn-secondary:hover { background: #c8c8c8; }
  .essay-btn-danger { background: #d9534f; color: #fff; }
  .essay-btn-danger:hover { background: #b52e2a; }
  .essay-saved-indicator { font-size: 12px; color: #888; flex: 1; }
  .essay-submitted-label { font-weight: 600; margin-bottom: 0.5rem; }
  .essay-submitted-text { background: #f9f9f9; border: 1px solid #ddd; padding: 1rem; border-radius: 4px; min-height: 60px; }
  .essay-submitted-text :first-child { margin-top: 0; }
  .essay-submitted-text :last-child { margin-bottom: 0; }
  .essay-status { padding: 0.5rem 0.75rem; border-radius: 4px; margin-top: 1rem; }
  .essay-status-pending { background: #fff8e1; border: 1px solid #ffd54f; color: #f57f17; }
  .essay-grade { background: #e8f5e9; border: 1px solid #a5d6a7; padding: 1rem; border-radius: 4px; margin-top: 1rem; }
  .essay-grade-score { font-size: 1.1rem; margin-bottom: 0.5rem; }
  .essay-grade-comment { color: #555; }
  .essay-table { border-collapse: collapse; width: 100%; font-size: 14px; }
  .essay-table th, .essay-table td { padding: 6px 10px; border: 1px solid #ddd; text-align: left; }
  .essay-table th { background: #f0f0f0; }
  .essay-badge { padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; display: inline-block; }
  .essay-badge-submitted { background: #fff3e0; color: #e65100; }
  .essay-badge-graded { background: #e8f5e9; color: #2e7d32; }
  .essay-action-btn { background: none; border: 1px solid #ccc; border-radius: 3px; padding: 2px 8px; cursor: pointer; font-size: 12px; margin-right: 4px; }
  .essay-action-btn:hover { background: #f0f0f0; }
  .essay-grade-panel { border: 2px solid #4a90d9; border-radius: 8px; padding: 1.5rem; margin-top: 1.5rem; background: #fafcff; }
  .essay-grade-panel h3 { margin-top: 0; }
  .essay-criteria-box { background: #f3f0ff; border: 1px solid #c4b8ff; padding: 0.75rem; border-radius: 4px; margin-bottom: 1rem; }
  .essay-criteria-box :first-child { margin-top: 0; }
  .essay-criteria-box :last-child { margin-bottom: 0; }
  .essay-input { padding: 0.4rem 0.6rem; font-size: 14px; border: 1px solid #ccc; border-radius: 4px; width: 100px; }
`;

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

export function setup(activity) {
  const el = activity.element;
  const permission = activity.permission;
  const isEdit = permission === "edit";
  const isPlay = permission === "play";

  let instructions = activity.state.instructions || "";
  let criteria = activity.state.criteria || "";
  let submissions = activity.state.submissions || [];
  let draft = activity.state.draft || "";
  let submission = activity.state.submission || null;

  let pendingSubmissionText = null;
  let activeGradeUserId = null;

  function render() {
    if (isEdit) {
      renderEdit();
    } else if (isPlay) {
      renderPlay();
    } else {
      renderView();
    }
  }

  function renderView() {
    el.innerHTML = `
      <style>${CSS}</style>
      <div class="essay-wrap">
        <div class="essay-instructions">${marked.parse(instructions)}</div>
      </div>
    `;
  }

  function renderPlay() {
    const isSubmitted = submission !== null;
    const isGraded = isSubmitted && submission.status === "graded";
    let contentHtml = "";

    if (!isSubmitted) {
      contentHtml = `
        <div class="essay-section">
          <label class="essay-label" for="essay-draft">Your essay (markdown)</label>
          <textarea id="essay-draft" class="essay-textarea" placeholder="Write your essay here...">${escapeHtml(draft)}</textarea>
          <div class="essay-actions">
            <span class="essay-saved-indicator" id="essay-saved-indicator"></span>
            <button class="essay-btn essay-btn-secondary" id="essay-save-btn">Save Draft</button>
            <button class="essay-btn essay-btn-primary" id="essay-submit-btn">Submit</button>
          </div>
        </div>
      `;
    } else {
      let gradeHtml = "";
      if (!isGraded) {
        gradeHtml = `<div class="essay-status essay-status-pending">Submission received. Awaiting grade...</div>`;
      } else {
        const pct = Math.round(submission.grade * 100);
        const commentHtml = submission.grade_comment
          ? `<div class="essay-grade-comment">${marked.parse(submission.grade_comment)}</div>`
          : "";
        gradeHtml = `
          <div class="essay-grade">
            <div class="essay-grade-score">Grade: <strong>${pct}%</strong></div>
            ${commentHtml}
          </div>
        `;
      }
      contentHtml = `
        <div class="essay-section">
          <div class="essay-submitted-label">Your submitted essay:</div>
          <div class="essay-submitted-text">${marked.parse(submission.text || "")}</div>
          ${gradeHtml}
        </div>
      `;
    }

    el.innerHTML = `
      <style>${CSS}</style>
      <div class="essay-wrap">
        <div class="essay-instructions">${marked.parse(instructions)}</div>
        ${contentHtml}
      </div>
    `;

    if (!isSubmitted) {
      const textarea = el.querySelector("#essay-draft");
      const indicator = el.querySelector("#essay-saved-indicator");
      const saveBtn = el.querySelector("#essay-save-btn");
      const submitBtn = el.querySelector("#essay-submit-btn");

      textarea.addEventListener("input", () => {
        if (indicator) indicator.textContent = "Unsaved changes";
      });

      saveBtn.addEventListener("click", () => {
        const text = textarea.value;
        draft = text;
        if (indicator) indicator.textContent = "Saving...";
        activity.sendAction("essay.save", text);
      });

      submitBtn.addEventListener("click", () => {
        const text = textarea.value;
        if (!text.trim()) {
          alert("Please write something before submitting.");
          return;
        }
        if (!confirm("Submit your essay? You will not be able to edit it after submission.")) return;
        pendingSubmissionText = text;
        activity.sendAction("essay.submit", text);
      });
    }
  }

  function renderEdit() {
    const subRows = (submissions || [])
      .map((s) => {
        const v = s.value || {};
        const statusClass = `essay-badge-${v.status || "submitted"}`;
        const statusBadge = `<span class="essay-badge ${statusClass}">${escapeHtml(v.status || "")}</span>`;
        const gradeCell =
          v.status === "graded" && typeof v.grade === "number"
            ? `${Math.round(v.grade * 100)}%`
            : "—";
        return `
          <tr data-user-id="${escapeHtml(v.user_id || "")}">
            <td>${escapeHtml(v.user_id || "")}</td>
            <td>${statusBadge}</td>
            <td>${gradeCell}</td>
            <td>
              <button class="essay-action-btn essay-grade-btn" data-user-id="${escapeHtml(v.user_id || "")}">Grade</button>
              <button class="essay-action-btn essay-unsubmit-btn" data-user-id="${escapeHtml(v.user_id || "")}">Un-submit</button>
              <button class="essay-action-btn essay-delete-btn" data-user-id="${escapeHtml(v.user_id || "")}">Delete</button>
            </td>
          </tr>
        `;
      })
      .join("");

    const subsTable =
      submissions && submissions.length > 0
        ? `<table class="essay-table">
             <thead><tr><th>Student</th><th>Status</th><th>Grade</th><th>Actions</th></tr></thead>
             <tbody>${subRows}</tbody>
           </table>`
        : "<p>No submissions yet.</p>";

    el.innerHTML = `
      <style>${CSS}</style>
      <div class="essay-wrap">
        <div class="essay-section">
          <h3>Configuration</h3>
          <label class="essay-label" for="essay-instructions-input">Instructions (markdown, visible to students)</label>
          <textarea id="essay-instructions-input" class="essay-textarea">${escapeHtml(instructions)}</textarea>
          <label class="essay-label" for="essay-criteria-input">Evaluation criteria (markdown, hidden from students)</label>
          <textarea id="essay-criteria-input" class="essay-textarea">${escapeHtml(criteria)}</textarea>
          <div class="essay-actions">
            <button class="essay-btn essay-btn-primary" id="essay-config-save-btn">Save Configuration</button>
          </div>
        </div>
        <div class="essay-section">
          <h3>Submissions</h3>
          ${subsTable}
        </div>
        <div id="essay-grade-panel"></div>
      </div>
    `;

    el.querySelector("#essay-config-save-btn").addEventListener("click", () => {
      const inst = el.querySelector("#essay-instructions-input").value;
      const crit = el.querySelector("#essay-criteria-input").value;
      activity.sendAction("config.save", { instructions: inst, criteria: crit });
    });

    el.querySelectorAll(".essay-grade-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        showGradePanel(btn.dataset.userId);
      });
    });

    el.querySelectorAll(".essay-unsubmit-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const u = btn.dataset.userId;
        if (confirm(`Un-submit essay for "${u}"? Their submission will be removed and they will be able to edit again.`)) {
          activity.sendAction("essay.unsubmit", { user_id: u });
        }
      });
    });

    el.querySelectorAll(".essay-delete-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const u = btn.dataset.userId;
        if (confirm(`Delete essay and draft for "${u}"? This cannot be undone.`)) {
          activity.sendAction("essay.delete", { user_id: u });
        }
      });
    });

    if (activeGradeUserId) {
      showGradePanel(activeGradeUserId);
    }
  }

  function showGradePanel(targetUserId) {
    activeGradeUserId = targetUserId;
    const panel = el.querySelector("#essay-grade-panel");
    if (!panel) return;

    const sub = (submissions || []).find((s) => (s.value || {}).user_id === targetUserId);
    const v = sub ? sub.value : null;
    const text = v ? v.text || "" : "";
    const currentGrade = v && v.status === "graded" && typeof v.grade === "number" ? v.grade : 0;
    const currentComment = v && v.grade_comment ? v.grade_comment : "";
    const criteriaHtml = criteria
      ? `<div class="essay-criteria-box"><strong>Evaluation criteria:</strong>${marked.parse(criteria)}</div>`
      : "";

    panel.innerHTML = `
      <div class="essay-grade-panel">
        <h3>Grade: ${escapeHtml(targetUserId)}</h3>
        ${criteriaHtml}
        <div class="essay-submitted-label">Submitted essay:</div>
        <div class="essay-submitted-text">${marked.parse(text)}</div>
        <label class="essay-label" for="essay-grade-input">Grade (0.0 – 1.0)</label>
        <input type="number" id="essay-grade-input" min="0" max="1" step="0.01" value="${currentGrade}" class="essay-input" />
        <label class="essay-label" for="essay-grade-comment-input">Comment (markdown, optional)</label>
        <textarea id="essay-grade-comment-input" class="essay-textarea">${escapeHtml(currentComment)}</textarea>
        <div class="essay-actions">
          <button class="essay-btn essay-btn-primary" id="essay-submit-grade-btn">Submit Grade</button>
          <button class="essay-btn essay-btn-secondary" id="essay-cancel-grade-btn">Close</button>
        </div>
      </div>
    `;

    panel.querySelector("#essay-submit-grade-btn").addEventListener("click", () => {
      const grade = parseFloat(panel.querySelector("#essay-grade-input").value);
      const gradeComment = panel.querySelector("#essay-grade-comment-input").value;
      if (isNaN(grade) || grade < 0 || grade > 1) {
        alert("Grade must be a number between 0.0 and 1.0");
        return;
      }
      activity.sendAction("essay.grade", {
        user_id: targetUserId,
        grade,
        grade_comment: gradeComment,
      });
      activeGradeUserId = null;
      panel.innerHTML = "";
    });

    panel.querySelector("#essay-cancel-grade-btn").addEventListener("click", () => {
      activeGradeUserId = null;
      panel.innerHTML = "";
    });
  }

  activity.onEvent = (name, value) => {
    if (name === "fields.change.instructions") {
      instructions = value;
      render();
    } else if (name === "fields.change.criteria") {
      criteria = value;
      render();
    } else if (name === "essay.saved") {
      const indicator = el.querySelector("#essay-saved-indicator");
      if (indicator) indicator.textContent = "Saved";
    } else if (name === "essay.submitted") {
      submission = {
        text: pendingSubmissionText !== null ? pendingSubmissionText : draft,
        status: "submitted",
        grade: 0,
        grade_comment: "",
      };
      pendingSubmissionText = null;
      render();
    } else if (name === "essay.graded") {
      if (submission) {
        submission = {
          ...submission,
          status: "graded",
          grade: value.grade,
          grade_comment: value.grade_comment,
        };
      }
      render();
    } else if (name === "submissions.changed") {
      submissions = value;
      render();
    }
  };

  render();
}
