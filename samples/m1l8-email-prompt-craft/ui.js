// UI for email-prompt-craft.
// Edit mode: course staff configure the Anthropic API key.
// Play mode: student picks a scenario, writes a prompt, generates an email
// with Claude Haiku, iterates, then submits for automatic rubric grading.
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
  .epc { font-family: sans-serif; max-width: 720px; color: #1d2029; }
  .epc h3 { margin: 0 0 0.5rem; }
  .epc-section { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
  .epc-field { margin-bottom: 0.75rem; }
  .epc-field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
  .epc-field select, .epc-field textarea, .epc-field input {
    width: 100%; padding: 0.5rem; box-sizing: border-box; font-family: inherit; font-size: 0.9rem;
    border: 1px solid #b0b6bf; border-radius: 4px;
  }
  .epc-field textarea { min-height: 120px; resize: vertical; }
  .epc-hint { font-size: 0.8rem; color: #6c7688; margin-top: 0.25rem; }
  .epc-btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 1.1rem; cursor: pointer; border: none; border-radius: 4px;
    background: #0075b4; color: #fff; font-size: 0.9rem;
  }
  .epc-btn:hover { background: #005f92; }
  .epc-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .epc-btn-secondary { background: #6c7688; }
  .epc-btn-secondary:hover { background: #565f70; }
  .epc-spinner {
    display: none; width: 12px; height: 12px; flex: 0 0 auto;
    border: 2px solid rgba(255, 255, 255, 0.4); border-top-color: #fff;
    border-radius: 50%; animation: epc-spin 0.7s linear infinite;
  }
  .epc-btn.is-busy .epc-spinner { display: inline-block; }
  @keyframes epc-spin { to { transform: rotate(360deg); } }
  .epc-output { background: #f8f9fa; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.75rem; white-space: pre-wrap; font-size: 0.9rem; margin-top: 0.5rem; }
  .epc-status { margin-top: 0.5rem; font-size: 0.875rem; }
  .epc-status.error { color: #b52626; }
  .epc-status.success { color: #1b7a3d; }
  .epc-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
  .epc-badge.configured { background: #d4edda; color: #155724; }
  .epc-badge.not-configured { background: #fff3cd; color: #856404; }
  .epc-checklist { font-size: 0.85rem; color: #444; padding-left: 1.1rem; }
  .epc-grade-card { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-top: 1rem; }
  .epc-grade-total { font-size: 1.8rem; font-weight: 700; }
  .epc-grade-letter { font-size: 1.1rem; font-weight: 700; padding: 0.1rem 0.6rem; border-radius: 4px; margin-left: 0.5rem; }
  .epc-grade-letter.A, .epc-grade-letter.B { background: #d4edda; color: #155724; }
  .epc-grade-letter.C { background: #fff3cd; color: #856404; }
  .epc-grade-letter.F { background: #f8d7da; color: #721c24; }
  .epc-criteria { display: flex; gap: 0.75rem; margin: 0.75rem 0; }
  .epc-criterion { flex: 1; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.5rem; text-align: center; }
  .epc-criterion .score { font-size: 1.3rem; font-weight: 700; }
  .epc-flags { color: #b52626; font-size: 0.85rem; }
  .epc-locked { color: #6c7688; font-style: italic; }
</style>
`;

const SCENARIO_OPTIONS = [
  ["client_followup", "Client follow-up after a meeting"],
  ["decline_request", "Declining a request diplomatically"],
  ["team_intro", "Introducing yourself to a new team"],
  ["escalate_issue", "Escalating an issue to management"],
  ["apology_service", "Apologizing for a service failure"],
  ["cold_outreach", "Cold outreach to a potential partner"],
];

function renderGradeCard(grade) {
  if (!grade || typeof grade.weighted_total !== "number") return "";
  const letter = escapeHtml(grade.letter_grade || "");
  const flags = Array.isArray(grade.flags) && grade.flags.length
    ? `<ul class="epc-flags">${grade.flags.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : "";
  return `
    <div class="epc-grade-card">
      <span class="epc-grade-total">${Math.round(grade.weighted_total)}%</span>
      <span class="epc-grade-letter ${letter}">${letter}</span>
      <div class="epc-criteria">
        <div class="epc-criterion"><div>Technique (50%)</div><div class="score">${grade.scores.a}/3</div></div>
        <div class="epc-criterion"><div>Prompt Quality (25%)</div><div class="score">${grade.scores.b}/3</div></div>
        <div class="epc-criterion"><div>Output Quality (25%)</div><div class="score">${grade.scores.c}/3</div></div>
      </div>
      <p>${escapeHtml(grade.feedback || "")}</p>
      ${flags}
      <p class="epc-hint">Passing threshold: 55%. Confidence: ${escapeHtml(grade.confidence || "n/a")}.</p>
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
      <div class="epc">
        <div class="epc-section">
          <h3>AI API Key
            <span class="epc-badge ${configured ? "configured" : "not-configured"}">
              ${configured ? "Configured" : "Not configured"}
            </span>
          </h3>
          <p class="epc-hint">This activity calls Anthropic's Claude Haiku to generate and grade student emails. Paste a valid Anthropic API key (starts with <code>sk-ant-</code>) here once per course — it's stored server-side and never shown again.</p>
          <div class="epc-field">
            <label for="epc-api-key">Anthropic API key</label>
            <input type="password" id="epc-api-key" placeholder="sk-ant-..." autocomplete="off" />
          </div>
          <a href="#" class="epc-btn" id="epc-save-key">Save key</a>
          <div class="epc-status" id="epc-key-status"></div>
        </div>
        <div class="epc-section">
          <h3>Preview</h3>
          <p class="epc-hint">Students pick one of six email scenarios, write a prompt, generate the email with AI, iterate at least once, then submit for automatic rubric grading (Technique 50% / Prompt Quality 25% / Output Quality 25%, 55% to pass).</p>
        </div>
      </div>
    `;

    element.querySelector("#epc-save-key").addEventListener("click", async (e) => {
      e.preventDefault();
      const key = element.querySelector("#epc-api-key").value.trim();
      const statusEl = element.querySelector("#epc-key-status");
      if (!key) {
        statusEl.textContent = "Enter a key first.";
        statusEl.className = "epc-status error";
        return;
      }
      try {
        await activity.sendAction("credentials.save", { haiku_api_key: key });
        statusEl.textContent = "Saved.";
        statusEl.className = "epc-status success";
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "epc-status error";
      }
    });
  }

  function renderViewView(state) {
    element.innerHTML = `
      ${STYLE}
      <div class="epc">
        <h3>Professional Email — Prompt Craft</h3>
        ${state.submitted
          ? `<p><strong>Scenario:</strong> ${escapeHtml((SCENARIO_OPTIONS.find((s) => s[0] === state.scenario) || [, state.scenario])[1])}</p>
             <p><strong>Final prompt:</strong></p><div class="epc-output">${escapeHtml(state.prompt_text)}</div>
             <p><strong>Generated email:</strong></p><div class="epc-output">${escapeHtml(state.output_text)}</div>
             ${renderGradeCard(state.grade_result)}`
          : `<p class="epc-locked">Not yet submitted.</p>`}
      </div>
    `;
  }

  function renderPlayView(state) {
    if (state.submitted) {
      element.innerHTML = `
        ${STYLE}
        <div class="epc">
          <h3>Professional Email — Prompt Craft</h3>
          <p class="epc-locked">Submitted — this activity is now locked.</p>
          <p><strong>Your final prompt:</strong></p><div class="epc-output">${escapeHtml(state.prompt_text)}</div>
          <p><strong>Generated email:</strong></p><div class="epc-output">${escapeHtml(state.output_text)}</div>
          ${renderGradeCard(state.grade_result)}
        </div>
      `;
      return;
    }

    const scenario = state.scenario || "";
    const attemptCount = state.attempt_count || 0;
    const canSubmit = attemptCount >= MIN_ATTEMPTS_BEFORE_SUBMIT && !!state.output_text;

    element.innerHTML = `
      ${STYLE}
      <div class="epc">
        <h3>Professional Email — Prompt Craft</h3>
        <p class="epc-hint">Pick a scenario, write a prompt using at least 2 of the 3 Craft techniques (Role Assignment, Context &amp; Constraints, Format &amp; Success Criteria), generate the email, then iterate at least once before submitting.</p>

        ${state.grade_result && typeof state.grade_result.weighted_total === "number" && !state.grade_result.passed
          ? `<div class="epc-section">
               <p class="epc-status error"><strong>Your last submission did not meet the passing threshold.</strong> Review the feedback below, revise your prompt, and submit again.</p>
               ${renderGradeCard(state.grade_result)}
             </div>`
          : ""}

        <div class="epc-section">
          <div class="epc-field">
            <label for="epc-scenario">Scenario</label>
            <select id="epc-scenario">
              <option value="">— select —</option>
              ${SCENARIO_OPTIONS.map(
                ([id, label]) => `<option value="${id}" ${id === scenario ? "selected" : ""}>${escapeHtml(label)}</option>`
              ).join("")}
            </select>
          </div>
          <div class="epc-field">
            <label for="epc-prompt">Your prompt</label>
            <textarea id="epc-prompt" placeholder="You are a... Write to... because... Keep it under ... words...">${escapeHtml(state.prompt_text || "")}</textarea>
          </div>
          <a href="#" class="epc-btn" id="epc-generate">
            <span class="epc-spinner" id="epc-generate-spinner"></span>
            <span id="epc-generate-label">Generate email</span>
          </a>
          <span class="epc-hint">Attempts so far: ${attemptCount} (need ${MIN_ATTEMPTS_BEFORE_SUBMIT}+ to submit)</span>
          <div class="epc-status" id="epc-gen-status"></div>
        </div>

        ${state.output_text
          ? `<div class="epc-section">
               <h3>Generated email</h3>
               <div class="epc-output" id="epc-output">${escapeHtml(state.output_text)}</div>
             </div>`
          : ""}

        <a href="#" class="epc-btn ${canSubmit ? "" : "epc-btn-secondary"}" id="epc-submit" ${canSubmit ? "" : "disabled"}>
          <span class="epc-spinner" id="epc-submit-spinner"></span>
          <span id="epc-submit-label">Submit for grading</span>
        </a>
        <div class="epc-status" id="epc-submit-status"></div>
      </div>
    `;

    element.querySelector("#epc-generate").addEventListener("click", async (e) => {
      e.preventDefault();
      const scenarioVal = element.querySelector("#epc-scenario").value;
      const promptVal = element.querySelector("#epc-prompt").value.trim();
      const statusEl = element.querySelector("#epc-gen-status");
      const btn = element.querySelector("#epc-generate");
      if (!scenarioVal) {
        statusEl.textContent = "Choose a scenario first.";
        statusEl.className = "epc-status error";
        return;
      }
      if (!promptVal) {
        statusEl.textContent = "Write a prompt first.";
        statusEl.className = "epc-status error";
        return;
      }
      btn.setAttribute("disabled", "disabled");
      btn.classList.add("is-busy");
      statusEl.textContent = "Generating — this can take a few seconds…";
      statusEl.className = "epc-status";
      try {
        if (scenarioVal !== activity.state.scenario) {
          await activity.sendAction("scenario.select", scenarioVal);
        }
        await activity.sendAction("email.generate", promptVal);
        // render() (triggered by the "email.generated" event above) already
        // rebuilds this button as part of showing the result, but that's an
        // indirect/implicit path. Clear the busy state explicitly too, right
        // here, so "spinner gone" is never decoupled from "response back" —
        // this is a no-op if the button element was already replaced.
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      } catch (err) {
        statusEl.textContent = "Generate failed: " + err;
        statusEl.className = "epc-status error";
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      }
    });

    element.querySelector("#epc-submit").addEventListener("click", async (e) => {
      e.preventDefault();
      if (!canSubmit) return;
      const statusEl = element.querySelector("#epc-submit-status");
      const btn = element.querySelector("#epc-submit");
      btn.setAttribute("disabled", "disabled");
      btn.classList.add("is-busy");
      statusEl.textContent = "Grading — this can take a few seconds…";
      statusEl.className = "epc-status";
      try {
        await activity.sendAction("email.submit", {});
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      } catch (err) {
        statusEl.textContent = "Submit failed: " + err;
        statusEl.className = "epc-status error";
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      }
    });
  }

  activity.onEvent = (name, value) => {
    if (name === "fields.change.scenario") {
      activity.state.scenario = value;
    } else if (name === "email.generated") {
      activity.state.prompt_text = value.prompt;
      activity.state.output_text = value.output;
      activity.state.attempt_count = value.attempt_count;
      render();
      const statusEl = element.querySelector("#epc-gen-status");
      if (statusEl) {
        statusEl.textContent = "Generated. Review it, then iterate at least once before submitting.";
        statusEl.className = "epc-status success";
      }
      return;
    } else if (name === "email.graded") {
      activity.state.grade_result = value;
      activity.state.submitted = !!value.passed;
      render();
      return;
    } else if (name === "generation.error") {
      const statusEl =
        element.querySelector("#epc-gen-status") ||
        element.querySelector("#epc-submit-status") ||
        element.querySelector("#epc-key-status");
      if (statusEl) {
        statusEl.textContent = value;
        statusEl.className = "epc-status error";
      }
      const genBtn = element.querySelector("#epc-generate");
      if (genBtn) {
        genBtn.removeAttribute("disabled");
        genBtn.classList.remove("is-busy");
      }
      const submitBtn = element.querySelector("#epc-submit");
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
