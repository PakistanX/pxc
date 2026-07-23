// UI for m2l3-meeting-documentation.
// Edit mode: course staff configure the Anthropic API key.
// Play mode: student pastes a transcript, writes a prompt template,
// generates a 5-section summary with Claude Haiku, refines it, documents
// the refinement, then submits for automatic rubric grading.
// View mode: read-only summary of the student's final submission + grade.

const MIN_ATTEMPTS_BEFORE_SUBMIT = 2;

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const STYLE = `
<style>
  .m2l3 { font-family: sans-serif; max-width: 760px; color: #1d2029; }
  .m2l3 h3 { margin: 0 0 0.5rem; }
  .m2l3-section { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
  .m2l3-field { margin-bottom: 0.75rem; }
  .m2l3-field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
  .m2l3-field textarea, .m2l3-field input {
    width: 100%; padding: 0.5rem; box-sizing: border-box; font-family: inherit; font-size: 0.9rem;
    border: 1px solid #b0b6bf; border-radius: 4px;
  }
  .m2l3-field textarea { min-height: 110px; resize: vertical; }
  .m2l3-field textarea.small { min-height: 70px; }
  .m2l3-hint { font-size: 0.8rem; color: #6c7688; margin-top: 0.25rem; }
  .m2l3-btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 1.1rem; cursor: pointer; border: none; border-radius: 4px;
    background: #0075b4; color: #fff; font-size: 0.9rem;
  }
  .m2l3-btn:hover { background: #005f92; }
  .m2l3-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .m2l3-btn-secondary { background: #6c7688; }
  .m2l3-spinner {
    display: none; width: 12px; height: 12px; flex: 0 0 auto;
    border: 2px solid rgba(255, 255, 255, 0.4); border-top-color: #fff;
    border-radius: 50%; animation: m2l3-spin 0.7s linear infinite;
  }
  .m2l3-btn.is-busy .m2l3-spinner { display: inline-block; }
  @keyframes m2l3-spin { to { transform: rotate(360deg); } }
  .m2l3-output { background: #f8f9fa; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.75rem; white-space: pre-wrap; font-size: 0.9rem; margin-top: 0.5rem; }
  .m2l3-status { margin-top: 0.5rem; font-size: 0.875rem; }
  .m2l3-status.error { color: #b52626; }
  .m2l3-status.success { color: #1b7a3d; }
  .m2l3-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
  .m2l3-badge.configured { background: #d4edda; color: #155724; }
  .m2l3-badge.not-configured { background: #fff3cd; color: #856404; }
  .m2l3-grade-card { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-top: 1rem; }
  .m2l3-grade-total { font-size: 1.8rem; font-weight: 700; }
  .m2l3-grade-letter { font-size: 1.1rem; font-weight: 700; padding: 0.1rem 0.6rem; border-radius: 4px; margin-left: 0.5rem; }
  .m2l3-grade-letter.A, .m2l3-grade-letter.B { background: #d4edda; color: #155724; }
  .m2l3-grade-letter.C { background: #fff3cd; color: #856404; }
  .m2l3-grade-letter.F { background: #f8d7da; color: #721c24; }
  .m2l3-criteria { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 0.75rem 0; }
  .m2l3-criterion { flex: 1 1 40%; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.5rem; text-align: center; }
  .m2l3-criterion .verdict { font-size: 1.3rem; font-weight: 700; }
  .m2l3-criterion .verdict.Y { color: #1b7a3d; }
  .m2l3-criterion .verdict.N { color: #b52626; }
  .m2l3-flags { color: #b52626; font-size: 0.85rem; }
  .m2l3-locked { color: #6c7688; font-style: italic; }
</style>
`;

const CRITERIA_LABELS = [
  ["c1_transcript_or_notes", "Transcript / Notes"],
  ["c2_prompt_template_design", "Prompt Template Design"],
  ["c3_five_section_output", "Five-Section Output"],
  ["c4_action_item_completeness", "Action Item Completeness"],
];

function renderGradeCard(grade) {
  if (!grade || typeof grade.weighted_total !== "number") return "";
  const letter = escapeHtml(grade.letter_grade || "");
  const criteria = CRITERIA_LABELS.map(([key, label]) => {
    const verdict = escapeHtml((grade.criteria && grade.criteria[key]) || "?");
    return `<div class="m2l3-criterion"><div>${label}</div><div class="verdict ${verdict}">${verdict}</div></div>`;
  }).join("");
  const flags = Array.isArray(grade.flags) && grade.flags.length
    ? `<ul class="m2l3-flags">${grade.flags.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : "";
  return `
    <div class="m2l3-grade-card">
      <span class="m2l3-grade-total">${Math.round(grade.weighted_total)}%</span>
      <span class="m2l3-grade-letter ${letter}">${letter}</span>
      <div class="m2l3-criteria">${criteria}</div>
      <p>${escapeHtml(grade.feedback || "")}</p>
      ${flags}
      <p class="m2l3-hint">Passing threshold: 50%. Confidence: ${escapeHtml(grade.confidence || "n/a")}.</p>
    </div>
  `;
}

export function setup(activity) {
  const element = activity.element;
  const permission = activity.permission;

  function render() {
    const state = activity.state;
    if (permission === "edit") {
      renderEditView(state);
    } else if (permission === "play") {
      renderPlayView(state);
    } else {
      renderViewView(state);
    }
  }

  function renderEditView(state) {
    const configured = !!state.credentials_configured;
    element.innerHTML = `
      ${STYLE}
      <div class="m2l3">
        <div class="m2l3-section">
          <h3>AI API Key
            <span class="m2l3-badge ${configured ? "configured" : "not-configured"}">
              ${configured ? "Configured" : "Not configured"}
            </span>
          </h3>
          <p class="m2l3-hint">This activity calls Anthropic's Claude Haiku to generate meeting summaries and grade submissions. Paste a valid Anthropic API key (starts with <code>sk-ant-</code>) here once per course — it's stored server-side and never shown again.</p>
          <div class="m2l3-field">
            <label for="m2l3-api-key">Anthropic API key</label>
            <input type="password" id="m2l3-api-key" placeholder="sk-ant-..." autocomplete="off" />
          </div>
          <a href="#" class="m2l3-btn" id="m2l3-save-key">Save key</a>
          <div class="m2l3-status" id="m2l3-key-status"></div>
        </div>
        <div class="m2l3-section">
          <h3>Preview</h3>
          <p class="m2l3-hint">Students paste a meeting transcript, write a prompt template (Role, Context &amp; Constraints, Format, Task Decomposition), generate a 5-section summary, refine it at least once, document the refinement, then submit for automatic rubric grading (4 binary criteria, 25% each, 50% to pass).</p>
        </div>
      </div>
    `;

    element.querySelector("#m2l3-save-key").addEventListener("click", async (e) => {
      e.preventDefault();
      const key = element.querySelector("#m2l3-api-key").value.trim();
      const statusEl = element.querySelector("#m2l3-key-status");
      if (!key) {
        statusEl.textContent = "Enter a key first.";
        statusEl.className = "m2l3-status error";
        return;
      }
      try {
        await activity.sendAction("credentials.save", { haiku_api_key: key });
        statusEl.textContent = "Saved.";
        statusEl.className = "m2l3-status success";
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m2l3-status error";
      }
    });
  }

  function renderViewView(state) {
    element.innerHTML = `
      ${STYLE}
      <div class="m2l3">
        <h3>Meeting Documentation System</h3>
        ${state.submitted
          ? `<p><strong>Final prompt template:</strong></p><div class="m2l3-output">${escapeHtml(state.prompt_text)}</div>
             <p><strong>AI-generated summary:</strong></p><div class="m2l3-output">${escapeHtml(state.output_text)}</div>
             ${renderGradeCard(state.grade_result)}`
          : `<p class="m2l3-locked">Not yet submitted.</p>`}
      </div>
    `;
  }

  function renderPlayView(state) {
    if (state.submitted) {
      element.innerHTML = `
        ${STYLE}
        <div class="m2l3">
          <h3>Meeting Documentation System</h3>
          <p class="m2l3-locked">Submitted — this activity is now locked.</p>
          <p><strong>Your final prompt template:</strong></p><div class="m2l3-output">${escapeHtml(state.prompt_text)}</div>
          <p><strong>AI-generated summary:</strong></p><div class="m2l3-output">${escapeHtml(state.output_text)}</div>
          <p><strong>Refinement note:</strong></p><div class="m2l3-output">${escapeHtml(state.refinement_note)}</div>
          ${renderGradeCard(state.grade_result)}
        </div>
      `;
      return;
    }

    const attemptCount = state.attempt_count || 0;
    const meetsAttemptThreshold = attemptCount >= MIN_ATTEMPTS_BEFORE_SUBMIT;
    const canSubmit = meetsAttemptThreshold && !!state.output_text && !!state.refinement_note;
    const canSaveRefinementNow = meetsAttemptThreshold && !!(state.refinement_note || "").trim();

    element.innerHTML = `
      ${STYLE}
      <div class="m2l3">
        <h3>Meeting Documentation System</h3>
        <p class="m2l3-hint">Paste a meeting transcript or detailed notes (10-20+ lines), write a prompt template using Role Assignment, Context &amp; Constraints, Format &amp; Success Criteria, and Task Decomposition, generate the summary, then refine your prompt and regenerate at least once before submitting.</p>

        ${state.grade_result && typeof state.grade_result.weighted_total === "number" && !state.grade_result.passed
          ? `<div class="m2l3-section">
               <p class="m2l3-status error"><strong>Your last submission did not meet the passing threshold.</strong> Review the feedback below, revise your prompt template or refinement note, and submit again.</p>
               ${renderGradeCard(state.grade_result)}
             </div>`
          : ""}

        <div class="m2l3-section">
          <div class="m2l3-field">
            <label for="m2l3-transcript">Meeting transcript / notes</label>
            <textarea id="m2l3-transcript" placeholder="Project Kickoff meeting, March 14. Attendees: ...">${escapeHtml(state.transcript_text || "")}</textarea>
          </div>
          <div class="m2l3-field">
            <label for="m2l3-prompt">Your prompt template</label>
            <textarea id="m2l3-prompt" placeholder="You are an executive assistant known for... Given the following meeting transcript, produce a structured summary with exactly these five sections: ...">${escapeHtml(state.prompt_text || "")}</textarea>
          </div>
          <a href="#" class="m2l3-btn" id="m2l3-generate">
            <span class="m2l3-spinner" id="m2l3-generate-spinner"></span>
            <span id="m2l3-generate-label">Generate summary</span>
          </a>
          <span class="m2l3-hint">Attempts so far: ${attemptCount} (need ${MIN_ATTEMPTS_BEFORE_SUBMIT}+ to submit)</span>
          <div class="m2l3-status" id="m2l3-gen-status"></div>
        </div>

        ${state.output_text
          ? `<div class="m2l3-section">
               <h3>AI-generated summary</h3>
               <div class="m2l3-output" id="m2l3-output">${escapeHtml(state.output_text)}</div>
             </div>`
          : ""}

        <div class="m2l3-section">
          <div class="m2l3-field">
            <label for="m2l3-refinement">Refinement note — what did you change and why?</label>
            <textarea class="small" id="m2l3-refinement" placeholder="Initial output did not include decision owners. Added explicit instruction to name an owner per decision.">${escapeHtml(state.refinement_note || "")}</textarea>
          </div>
          <a href="#" class="m2l3-btn ${canSaveRefinementNow ? "" : "m2l3-btn-secondary"}" id="m2l3-save-refinement" ${canSaveRefinementNow ? "" : "disabled"}>Save refinement note</a>
          <div class="m2l3-status" id="m2l3-refinement-status"></div>
          ${!meetsAttemptThreshold
            ? `<p class="m2l3-hint">Generate at least ${MIN_ATTEMPTS_BEFORE_SUBMIT} times (refine your prompt and regenerate) before saving a refinement note.</p>`
            : ""}
        </div>

        <a href="#" class="m2l3-btn ${canSubmit ? "" : "m2l3-btn-secondary"}" id="m2l3-submit" ${canSubmit ? "" : "disabled"}>
          <span class="m2l3-spinner" id="m2l3-submit-spinner"></span>
          <span id="m2l3-submit-label">Submit for grading</span>
        </a>
        <div class="m2l3-status" id="m2l3-submit-status"></div>
      </div>
    `;

    element.querySelector("#m2l3-generate").addEventListener("click", async (e) => {
      e.preventDefault();
      const transcriptVal = element.querySelector("#m2l3-transcript").value.trim();
      const promptVal = element.querySelector("#m2l3-prompt").value.trim();
      const statusEl = element.querySelector("#m2l3-gen-status");
      const btn = element.querySelector("#m2l3-generate");
      if (!transcriptVal) {
        statusEl.textContent = "Paste your meeting transcript or notes first.";
        statusEl.className = "m2l3-status error";
        return;
      }
      if (!promptVal) {
        statusEl.textContent = "Write your prompt template first.";
        statusEl.className = "m2l3-status error";
        return;
      }
      btn.setAttribute("disabled", "disabled");
      btn.classList.add("is-busy");
      statusEl.textContent = "Generating — this can take a few seconds…";
      statusEl.className = "m2l3-status";
      try {
        await activity.sendAction("meeting.generate", { transcript: transcriptVal, prompt: promptVal });
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      } catch (err) {
        statusEl.textContent = "Generate failed: " + err;
        statusEl.className = "m2l3-status error";
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      }
    });

    const refinementTextarea = element.querySelector("#m2l3-refinement");
    const saveRefinementBtn = element.querySelector("#m2l3-save-refinement");

    function updateSaveRefinementButton() {
      const enabled = meetsAttemptThreshold && !!refinementTextarea.value.trim();
      saveRefinementBtn.classList.toggle("m2l3-btn-secondary", !enabled);
      if (enabled) {
        saveRefinementBtn.removeAttribute("disabled");
      } else {
        saveRefinementBtn.setAttribute("disabled", "disabled");
      }
    }

    refinementTextarea.addEventListener("input", updateSaveRefinementButton);

    saveRefinementBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      const noteVal = refinementTextarea.value.trim();
      const statusEl = element.querySelector("#m2l3-refinement-status");
      if (!meetsAttemptThreshold) {
        statusEl.textContent = "Generate at least " + MIN_ATTEMPTS_BEFORE_SUBMIT + " times first.";
        statusEl.className = "m2l3-status error";
        return;
      }
      if (!noteVal) {
        statusEl.textContent = "Write a note first.";
        statusEl.className = "m2l3-status error";
        return;
      }
      try {
        await activity.sendAction("meeting.save_refinement", noteVal);
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m2l3-status error";
      }
    });

    element.querySelector("#m2l3-submit").addEventListener("click", async (e) => {
      e.preventDefault();
      if (!canSubmit) return;
      const statusEl = element.querySelector("#m2l3-submit-status");
      const btn = element.querySelector("#m2l3-submit");
      btn.setAttribute("disabled", "disabled");
      btn.classList.add("is-busy");
      statusEl.textContent = "Grading — this can take a few seconds…";
      statusEl.className = "m2l3-status";
      try {
        await activity.sendAction("meeting.submit", {});
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      } catch (err) {
        statusEl.textContent = "Submit failed: " + err;
        statusEl.className = "m2l3-status error";
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      }
    });
  }

  activity.onEvent = (name, value) => {
    if (name === "meeting.generated") {
      activity.state.transcript_text = value.transcript;
      activity.state.prompt_text = value.prompt;
      activity.state.output_text = value.output;
      activity.state.attempt_count = value.attempt_count;
      render();
      const statusEl = element.querySelector("#m2l3-gen-status");
      if (statusEl) {
        statusEl.textContent = "Generated. Review it, refine your prompt, and regenerate before submitting.";
        statusEl.className = "m2l3-status success";
      }
      return;
    } else if (name === "refinement.saved") {
      activity.state.refinement_note = value.refinement_note;
      render();
      const statusEl = element.querySelector("#m2l3-refinement-status");
      if (statusEl) {
        statusEl.textContent = "Saved.";
        statusEl.className = "m2l3-status success";
      }
      return;
    } else if (name === "meeting.graded") {
      activity.state.grade_result = value;
      activity.state.submitted = !!value.passed;
      render();
      return;
    } else if (name === "generation.error") {
      const statusEl =
        element.querySelector("#m2l3-gen-status") ||
        element.querySelector("#m2l3-submit-status") ||
        element.querySelector("#m2l3-key-status");
      if (statusEl) {
        statusEl.textContent = value;
        statusEl.className = "m2l3-status error";
      }
      const genBtn = element.querySelector("#m2l3-generate");
      if (genBtn) {
        genBtn.removeAttribute("disabled");
        genBtn.classList.remove("is-busy");
      }
      const submitBtn = element.querySelector("#m2l3-submit");
      if (submitBtn) {
        submitBtn.classList.remove("is-busy");
        if ((activity.state.attempt_count || 0) >= MIN_ATTEMPTS_BEFORE_SUBMIT) {
          submitBtn.removeAttribute("disabled");
        }
      }
      return;
    } else if (name === "credentials.status") {
      activity.state.credentials_configured = value.configured;
    }
    render();
  };

  render();
}
