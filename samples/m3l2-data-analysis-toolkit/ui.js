// UI for m3l2-data-analysis-toolkit.
// Edit mode: course staff configure the Anthropic API key.
// Play mode: student downloads a dataset, picks it from a matching dropdown,
// documents the AI-generated description, 2 visualization title/captions,
// an executive summary, and the 3 stage prompts (Stage 2/3/4), then submits
// for automatic rubric grading. No in-app AI generation — students run the
// analysis with their own AI tool of choice and transcribe the results here
// (see sandbox.js's design note).
// View mode: read-only summary of the student's final submission + grade.

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const REQUIRED_VISUALIZATION_COUNT = 2;

const STYLE = `
<style>
  .m3l2 { font-family: sans-serif; max-width: 820px; color: #1d2029; }
  .m3l2 h3 { margin: 0 0 0.5rem; }
  .m3l2-section { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
  .m3l2-field { margin-bottom: 0.75rem; }
  .m3l2-field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
  .m3l2-field select, .m3l2-field textarea, .m3l2-field input {
    width: 100%; padding: 0.5rem; box-sizing: border-box; font-family: inherit; font-size: 0.9rem;
    border: 1px solid #b0b6bf; border-radius: 4px;
  }
  .m3l2-field textarea { min-height: 90px; resize: vertical; }
  .m3l2-field textarea.small { min-height: 60px; }
  .m3l2-hint { font-size: 0.8rem; color: #6c7688; margin-top: 0.25rem; }
  .m3l2-btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 1.1rem; cursor: pointer; border: none; border-radius: 4px;
    background: #0075b4; color: #fff; font-size: 0.9rem; margin-right: 0.5rem;
  }
  .m3l2-btn:hover { background: #005f92; }
  .m3l2-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .m3l2-btn-secondary { background: #6c7688; }
  .m3l2-spinner {
    display: none; width: 12px; height: 12px; flex: 0 0 auto;
    border: 2px solid rgba(255, 255, 255, 0.4); border-top-color: #fff;
    border-radius: 50%; animation: m3l2-spin 0.7s linear infinite;
  }
  .m3l2-btn.is-busy .m3l2-spinner { display: inline-block; }
  @keyframes m3l2-spin { to { transform: rotate(360deg); } }
  .m3l2-status { margin-top: 0.5rem; font-size: 0.875rem; }
  .m3l2-status.error { color: #b52626; }
  .m3l2-status.success { color: #1b7a3d; }
  .m3l2-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
  .m3l2-badge.configured { background: #d4edda; color: #155724; }
  .m3l2-badge.not-configured { background: #fff3cd; color: #856404; }
  .m3l2-viz { border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.6rem; margin-bottom: 0.6rem; }
  .m3l2-viz h4 { margin: 0 0 0.4rem; }
  .m3l2-output { background: #f8f9fa; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.75rem; white-space: pre-wrap; font-size: 0.9rem; margin-top: 0.5rem; }
  .m3l2-grade-card { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-top: 1rem; }
  .m3l2-grade-total { font-size: 1.8rem; font-weight: 700; }
  .m3l2-grade-letter { font-size: 1.1rem; font-weight: 700; padding: 0.1rem 0.6rem; border-radius: 4px; margin-left: 0.5rem; }
  .m3l2-grade-letter.A, .m3l2-grade-letter.B { background: #d4edda; color: #155724; }
  .m3l2-grade-letter.C { background: #fff3cd; color: #856404; }
  .m3l2-grade-letter.F { background: #f8d7da; color: #721c24; }
  .m3l2-criteria { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 0.75rem 0; }
  .m3l2-criterion { flex: 1 1 40%; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.5rem; text-align: center; }
  .m3l2-criterion .verdict { font-size: 1.3rem; font-weight: 700; }
  .m3l2-criterion .verdict.Y { color: #1b7a3d; }
  .m3l2-criterion .verdict.N { color: #b52626; }
  .m3l2-flags { color: #b52626; font-size: 0.85rem; }
  .m3l2-locked { color: #6c7688; font-style: italic; }
</style>
`;

const APPROVED_DATASETS = [
  "Sales / Revenue Data",
  "Survey Responses",
  "Website Analytics",
  "Urban Development",
];

const CRITERIA_LABELS = [
  ["c1_dataset_description", "Dataset Description"],
  ["c2_visualization_count", "Visualization Count"],
  ["c3_executive_summary", "Executive Summary"],
  ["c4_prompt_documentation", "Prompt Documentation"],
];

function renderGradeCard(grade) {
  if (!grade || typeof grade.weighted_total !== "number") return "";
  const letter = escapeHtml(grade.letter_grade || "");
  const criteria = CRITERIA_LABELS.map(([key, label]) => {
    const verdict = escapeHtml((grade.criteria && grade.criteria[key]) || "?");
    return `<div class="m3l2-criterion"><div>${label}</div><div class="verdict ${verdict}">${verdict}</div></div>`;
  }).join("");
  const flags = Array.isArray(grade.flags) && grade.flags.length
    ? `<ul class="m3l2-flags">${grade.flags.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : "";
  return `
    <div class="m3l2-grade-card">
      <span class="m3l2-grade-total">${Math.round(grade.weighted_total)}%</span>
      <span class="m3l2-grade-letter ${letter}">${letter}</span>
      <div class="m3l2-criteria">${criteria}</div>
      <p>${escapeHtml(grade.feedback || "")}</p>
      ${flags}
      <p class="m3l2-hint">Passing threshold: 50%. Confidence: ${escapeHtml(grade.confidence || "n/a")}.</p>
    </div>
  `;
}

function normalizeVisualizations(visualizations) {
  const result = [];
  for (let i = 0; i < REQUIRED_VISUALIZATION_COUNT; i++) {
    const v = (visualizations && visualizations[i]) || {};
    result.push({ title: v.title || "", caption: v.caption || "" });
  }
  return result;
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
      <div class="m3l2">
        <div class="m3l2-section">
          <h3>AI API Key
            <span class="m3l2-badge ${configured ? "configured" : "not-configured"}">
              ${configured ? "Configured" : "Not configured"}
            </span>
          </h3>
          <p class="m3l2-hint">This activity calls Anthropic's Claude Haiku to grade submissions. Paste a valid Anthropic API key (starts with <code>sk-ant-</code>) here once per course — it's stored server-side and never shown again.</p>
          <div class="m3l2-field">
            <label for="m3l2-api-key">Anthropic API key</label>
            <input type="password" id="m3l2-api-key" placeholder="sk-ant-..." autocomplete="off" />
          </div>
          <a href="#" class="m3l2-btn" id="m3l2-save-key">Save key</a>
          <div class="m3l2-status" id="m3l2-key-status"></div>
        </div>
        <div class="m3l2-section">
          <h3>Preview</h3>
          <p class="m3l2-hint">Students download one of four provided datasets, run a 5-stage analysis workflow with their own AI tool, then document their dataset choice, AI-generated description, 2 labeled visualizations, an executive summary, and 3 stage prompts (Stage 2/3/4) here for automatic rubric grading (4 binary criteria, 25% each, 50% to pass).</p>
        </div>
      </div>
    `;

    element.querySelector("#m3l2-save-key").addEventListener("click", async (e) => {
      e.preventDefault();
      const key = element.querySelector("#m3l2-api-key").value.trim();
      const statusEl = element.querySelector("#m3l2-key-status");
      if (!key) {
        statusEl.textContent = "Enter a key first.";
        statusEl.className = "m3l2-status error";
        return;
      }
      try {
        await activity.sendAction("credentials.save", { haiku_api_key: key });
        statusEl.textContent = "Saved.";
        statusEl.className = "m3l2-status success";
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m3l2-status error";
      }
    });
  }

  function renderViewView(state) {
    element.innerHTML = `
      ${STYLE}
      <div class="m3l2">
        <h3>Data Analysis Toolkit</h3>
        ${state.submitted
          ? `<p><strong>Dataset:</strong> ${escapeHtml(state.dataset)}</p>${renderGradeCard(state.grade_result)}`
          : `<p class="m3l2-locked">Not yet submitted.</p>`}
      </div>
    `;
  }

  function readDraftFromForm() {
    return {
      dataset: element.querySelector("#m3l2-dataset").value,
      ai_description: element.querySelector("#m3l2-ai-description").value.trim(),
      visualizations: Array.from(element.querySelectorAll(".m3l2-viz")).map((el) => ({
        title: el.querySelector(".m3l2-viz-title").value.trim(),
        caption: el.querySelector(".m3l2-viz-caption").value.trim(),
      })),
      executive_summary: element.querySelector("#m3l2-executive-summary").value.trim(),
      stage2_prompt: element.querySelector("#m3l2-stage2").value.trim(),
      stage3_prompt: element.querySelector("#m3l2-stage3").value.trim(),
      stage4_prompt: element.querySelector("#m3l2-stage4").value.trim(),
    };
  }

  function renderVisualizationsHtml(visualizations) {
    return visualizations
      .map(
        (v, i) => `
        <div class="m3l2-viz">
          <h4>Visualization ${i + 1}</h4>
          <div class="m3l2-field">
            <label>Title</label>
            <input class="m3l2-viz-title" type="text" placeholder="Descriptive, insight-driven title" value="${escapeHtml(v.title)}" />
          </div>
          <div class="m3l2-field">
            <label>Interpretive caption (what the pattern means, not just what the chart shows)</label>
            <textarea class="m3l2-viz-caption small">${escapeHtml(v.caption)}</textarea>
          </div>
        </div>`
      )
      .join("");
  }

  function renderPlayView(state) {
    if (state.submitted) {
      element.innerHTML = `
        ${STYLE}
        <div class="m3l2">
          <h3>Data Analysis Toolkit</h3>
          <p class="m3l2-locked">Submitted — this activity is now locked.</p>
          <p><strong>Dataset:</strong> ${escapeHtml(state.dataset)}</p>
          <p><strong>AI description:</strong></p><div class="m3l2-output">${escapeHtml(state.ai_description)}</div>
          <p><strong>Executive summary:</strong></p><div class="m3l2-output">${escapeHtml(state.executive_summary)}</div>
          ${renderGradeCard(state.grade_result)}
        </div>
      `;
      return;
    }

    const visualizations = normalizeVisualizations(state.visualizations);
    const dataset = state.dataset || "";

    element.innerHTML = `
      ${STYLE}
      <div class="m3l2">
        <h3>Data Analysis Toolkit</h3>
        <p class="m3l2-hint">Download the dataset below, pick it from the dropdown to match, then run the 5-stage analysis workflow (upload &amp; understand, explore, generate insights, visualize, summarize &amp; recommend) with your own AI tool. Document the results here.</p>
        <p><a href="${activity.getAssetUrl("Public_M3L2_Datasets.xlsx")}" target="_blank" rel="noopener">Download Public_M3L2_Datasets.xlsx</a></p>

        ${state.grade_result && typeof state.grade_result.weighted_total === "number" && !state.grade_result.passed
          ? `<div class="m3l2-section">
               <p class="m3l2-status error"><strong>Your last submission did not meet the passing threshold.</strong> Review the feedback below, revise your write-up, and submit again.</p>
               ${renderGradeCard(state.grade_result)}
             </div>`
          : ""}

        <div class="m3l2-section">
          <div class="m3l2-field">
            <label for="m3l2-dataset">Dataset</label>
            <select id="m3l2-dataset">
              <option value="">— select —</option>
              ${APPROVED_DATASETS.map((d) => `<option value="${escapeHtml(d)}" ${d === dataset ? "selected" : ""}>${escapeHtml(d)}</option>`).join("")}
            </select>
          </div>
          <div class="m3l2-field">
            <label for="m3l2-ai-description">AI-generated dataset description</label>
            <textarea id="m3l2-ai-description" placeholder="The dataset contains 250 rows and N columns. Columns include: ... No missing values detected. ...">${escapeHtml(state.ai_description || "")}</textarea>
          </div>
        </div>

        <div class="m3l2-section">
          <h3>Visualizations (exactly 2)</h3>
          <div id="m3l2-viz-container">${renderVisualizationsHtml(visualizations)}</div>
        </div>

        <div class="m3l2-section">
          <div class="m3l2-field">
            <label for="m3l2-executive-summary">Executive summary (100–150 words, lead with the key finding, include a specific actionable recommendation)</label>
            <textarea id="m3l2-executive-summary">${escapeHtml(state.executive_summary || "")}</textarea>
          </div>
        </div>

        <div class="m3l2-section">
          <h3>Stage prompts</h3>
          <div class="m3l2-field">
            <label for="m3l2-stage2">Stage 2 prompt</label>
            <textarea id="m3l2-stage2" class="small" placeholder="You are a senior data analyst. For the primary outcome column, calculate: mean, median, standard deviation, min, and max...">${escapeHtml(state.stage2_prompt || "")}</textarea>
          </div>
          <div class="m3l2-field">
            <label for="m3l2-stage3">Stage 3 prompt</label>
            <textarea id="m3l2-stage3" class="small" placeholder="Based on the statistics we just calculated, what are the 2 most important findings?...">${escapeHtml(state.stage3_prompt || "")}</textarea>
          </div>
          <div class="m3l2-field">
            <label for="m3l2-stage4">Stage 4 prompt</label>
            <textarea id="m3l2-stage4" class="small" placeholder="Create 2 charts for a management presentation...">${escapeHtml(state.stage4_prompt || "")}</textarea>
          </div>
        </div>

        <a href="#" class="m3l2-btn m3l2-btn-secondary" id="m3l2-save">
          <span class="m3l2-spinner" id="m3l2-save-spinner"></span>
          <span>Save draft</span>
        </a>
        <a href="#" class="m3l2-btn" id="m3l2-submit">
          <span class="m3l2-spinner" id="m3l2-submit-spinner"></span>
          <span>Submit for grading</span>
        </a>
        <div class="m3l2-status" id="m3l2-form-status"></div>
      </div>
    `;

    element.querySelector("#m3l2-save").addEventListener("click", async (e) => {
      e.preventDefault();
      const draft = readDraftFromForm();
      const statusEl = element.querySelector("#m3l2-form-status");
      const btn = element.querySelector("#m3l2-save");
      btn.classList.add("is-busy");
      try {
        await activity.sendAction("draft.save", draft);
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m3l2-status error";
      } finally {
        btn.classList.remove("is-busy");
      }
    });

    element.querySelector("#m3l2-submit").addEventListener("click", async (e) => {
      e.preventDefault();
      const draft = readDraftFromForm();
      const statusEl = element.querySelector("#m3l2-form-status");
      const btn = element.querySelector("#m3l2-submit");
      btn.setAttribute("disabled", "disabled");
      btn.classList.add("is-busy");
      statusEl.textContent = "Saving draft, then grading — this can take a few seconds…";
      statusEl.className = "m3l2-status";
      try {
        await activity.sendAction("draft.save", draft);
        await activity.sendAction("toolkit.submit", {});
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      } catch (err) {
        statusEl.textContent = "Submit failed: " + err;
        statusEl.className = "m3l2-status error";
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      }
    });
  }

  activity.onEvent = (name, value) => {
    if (name === "draft.saved") {
      activity.state.dataset = value.dataset;
      activity.state.ai_description = value.ai_description;
      activity.state.visualizations = value.visualizations;
      activity.state.executive_summary = value.executive_summary;
      activity.state.stage2_prompt = value.stage2_prompt;
      activity.state.stage3_prompt = value.stage3_prompt;
      activity.state.stage4_prompt = value.stage4_prompt;
      const statusEl = element.querySelector("#m3l2-form-status");
      if (statusEl) {
        statusEl.textContent = "Draft saved.";
        statusEl.className = "m3l2-status success";
      }
      return;
    } else if (name === "toolkit.graded") {
      activity.state.grade_result = value;
      activity.state.submitted = !!value.passed;
      render();
      return;
    } else if (name === "generation.error") {
      const statusEl = element.querySelector("#m3l2-form-status") || element.querySelector("#m3l2-key-status");
      if (statusEl) {
        statusEl.textContent = value;
        statusEl.className = "m3l2-status error";
      }
      const submitBtn = element.querySelector("#m3l2-submit");
      if (submitBtn) {
        submitBtn.removeAttribute("disabled");
        submitBtn.classList.remove("is-busy");
      }
      return;
    } else if (name === "credentials.status") {
      activity.state.credentials_configured = value.configured;
    }
    render();
  };

  render();
}
