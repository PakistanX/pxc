// UI for m2l5-presentation-builder.
// Edit mode: course staff configure the Anthropic API key.
// Play mode: student picks an approved topic, records >=3 labeled staged
// prompts, transcribes their 5-slide deck (title/bullets/notes per slide),
// saves the draft, then submits for automatic rubric grading. No in-app AI
// generation — students build the actual deck with their own AI tool of
// choice and transcribe the result here (see sandbox.js's design note).
// View mode: read-only summary of the student's final submission + grade.

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const MIN_STAGES = 3;
const MAX_STAGES = 6;
const SLIDE_COUNT = 5;
const STAGE_LABEL_PLACEHOLDERS = ["Outline", "Content", "Speaker Notes", "Visual Suggestions", "Stage 5", "Stage 6"];

const STYLE = `
<style>
  .m2l5 { font-family: sans-serif; max-width: 820px; color: #1d2029; }
  .m2l5 h3 { margin: 0 0 0.5rem; }
  .m2l5-section { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
  .m2l5-field { margin-bottom: 0.75rem; }
  .m2l5-field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
  .m2l5-field select, .m2l5-field textarea, .m2l5-field input,
  .m2l5-stage-header input, .m2l5-stage-text {
    width: 100%; padding: 0.5rem; box-sizing: border-box; font-family: inherit; font-size: 0.9rem;
    border: 1px solid #b0b6bf; border-radius: 4px;
  }
  .m2l5-field textarea, .m2l5-stage-text { min-height: 80px; resize: vertical; }
  .m2l5-hint { font-size: 0.8rem; color: #6c7688; margin-top: 0.25rem; }
  .m2l5-btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 1.1rem; cursor: pointer; border: none; border-radius: 4px;
    background: #0075b4; color: #fff; font-size: 0.9rem; margin-right: 0.5rem;
  }
  .m2l5-btn:hover { background: #005f92; }
  .m2l5-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .m2l5-btn-secondary { background: #6c7688; }
  .m2l5-btn-small { padding: 0.25rem 0.6rem; font-size: 0.8rem; }
  .m2l5-spinner {
    display: none; width: 12px; height: 12px; flex: 0 0 auto;
    border: 2px solid rgba(255, 255, 255, 0.4); border-top-color: #fff;
    border-radius: 50%; animation: m2l5-spin 0.7s linear infinite;
  }
  .m2l5-btn.is-busy .m2l5-spinner { display: inline-block; }
  @keyframes m2l5-spin { to { transform: rotate(360deg); } }
  .m2l5-status { margin-top: 0.5rem; font-size: 0.875rem; }
  .m2l5-status.error { color: #b52626; }
  .m2l5-status.success { color: #1b7a3d; }
  .m2l5-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
  .m2l5-badge.configured { background: #d4edda; color: #155724; }
  .m2l5-badge.not-configured { background: #fff3cd; color: #856404; }
  .m2l5-stage { border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.6rem; margin-bottom: 0.6rem; }
  .m2l5-stage-header { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.4rem; }
  .m2l5-stage-header input { flex: 1; }
  .m2l5-slide { border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.6rem; margin-bottom: 0.6rem; }
  .m2l5-slide h4 { margin: 0 0 0.4rem; }
  .m2l5-output { background: #f8f9fa; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.75rem; white-space: pre-wrap; font-size: 0.9rem; margin-top: 0.5rem; }
  .m2l5-grade-card { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-top: 1rem; }
  .m2l5-grade-total { font-size: 1.8rem; font-weight: 700; }
  .m2l5-grade-letter { font-size: 1.1rem; font-weight: 700; padding: 0.1rem 0.6rem; border-radius: 4px; margin-left: 0.5rem; }
  .m2l5-grade-letter.A, .m2l5-grade-letter.B { background: #d4edda; color: #155724; }
  .m2l5-grade-letter.C { background: #fff3cd; color: #856404; }
  .m2l5-grade-letter.F { background: #f8d7da; color: #721c24; }
  .m2l5-criteria { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 0.75rem 0; }
  .m2l5-criterion { flex: 1 1 30%; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.5rem; text-align: center; }
  .m2l5-criterion .verdict { font-size: 1.3rem; font-weight: 700; }
  .m2l5-criterion .verdict.Y { color: #1b7a3d; }
  .m2l5-criterion .verdict.N { color: #b52626; }
  .m2l5-flags { color: #b52626; font-size: 0.85rem; }
  .m2l5-locked { color: #6c7688; font-style: italic; }
</style>
`;

const APPROVED_TOPICS = [
  "Smart Cities and the Future of Urban Living",
  "How Social Media Shapes Human Behavior",
  "AI in Education: Benefits, Risks, and Possibilities",
  "Climate Change Solutions That Can Work Now",
  "Work and Careers in the Age of Automation",
  "The Psychology of Consumer Decisions",
];

const CRITERIA_LABELS = [
  ["c1_slide_count", "Slide Count"],
  ["c2_narrative_structure", "Narrative Structure"],
  ["c3_technique_usage", "Technique Usage"],
  ["c4_prompt_stages", "Prompt Stages"],
  ["c5_slide_text_quality", "Slide Text Quality"],
  ["c6_topic_validity", "Topic Validity"],
];

function renderGradeCard(grade) {
  if (!grade || typeof grade.weighted_total !== "number") return "";
  const letter = escapeHtml(grade.letter_grade || "");
  const criteria = CRITERIA_LABELS.map(([key, label]) => {
    const verdict = escapeHtml((grade.criteria && grade.criteria[key]) || "?");
    return `<div class="m2l5-criterion"><div>${label}</div><div class="verdict ${verdict}">${verdict}</div></div>`;
  }).join("");
  const flags = Array.isArray(grade.flags) && grade.flags.length
    ? `<ul class="m2l5-flags">${grade.flags.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : "";
  return `
    <div class="m2l5-grade-card">
      <span class="m2l5-grade-total">${Math.round(grade.weighted_total * 10) / 10}%</span>
      <span class="m2l5-grade-letter ${letter}">${letter}</span>
      <div class="m2l5-criteria">${criteria}</div>
      <p>${escapeHtml(grade.feedback || "")}</p>
      ${flags}
      <p class="m2l5-hint">Passing threshold: 66.7% (4 of 6 criteria). Confidence: ${escapeHtml(grade.confidence || "n/a")}.</p>
    </div>
  `;
}

function emptySlide() {
  return { title: "", bullets: ["", "", ""], notes: "" };
}

function normalizeSlides(slides) {
  const result = [];
  for (let i = 0; i < SLIDE_COUNT; i++) {
    const s = (slides && slides[i]) || {};
    const bullets = Array.isArray(s.bullets) ? s.bullets.slice(0, 3) : [];
    while (bullets.length < 3) bullets.push("");
    result.push({ title: s.title || "", bullets: bullets, notes: s.notes || "" });
  }
  return result;
}

function normalizeStages(stages) {
  if (Array.isArray(stages) && stages.length >= MIN_STAGES) {
    return stages.map((s) => ({ label: s.label || "", text: s.text || "" }));
  }
  const result = Array.isArray(stages) ? stages.slice() : [];
  while (result.length < MIN_STAGES) {
    result.push({ label: "", text: "" });
  }
  return result;
}

export function setup(activity) {
  const element = activity.element;
  const permission = activity.permission;
  let draftStages = [];
  let draftSlides = [];

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
      <div class="m2l5">
        <div class="m2l5-section">
          <h3>AI API Key
            <span class="m2l5-badge ${configured ? "configured" : "not-configured"}">
              ${configured ? "Configured" : "Not configured"}
            </span>
          </h3>
          <p class="m2l5-hint">This activity calls Anthropic's Claude Haiku to grade submissions. Paste a valid Anthropic API key (starts with <code>sk-ant-</code>) here once per course — it's stored server-side and never shown again.</p>
          <div class="m2l5-field">
            <label for="m2l5-api-key">Anthropic API key</label>
            <input type="password" id="m2l5-api-key" placeholder="sk-ant-..." autocomplete="off" />
          </div>
          <a href="#" class="m2l5-btn" id="m2l5-save-key">Save key</a>
          <div class="m2l5-status" id="m2l5-key-status"></div>
        </div>
        <div class="m2l5-section">
          <h3>Preview</h3>
          <p class="m2l5-hint">Students pick one of six approved topics, submit at least 3 labeled staged prompts (outline/content/notes/visuals), transcribe their 5-slide deck, then submit for automatic rubric grading (6 binary criteria, ~16.7% each, 66.7% to pass).</p>
        </div>
      </div>
    `;

    element.querySelector("#m2l5-save-key").addEventListener("click", async (e) => {
      e.preventDefault();
      const key = element.querySelector("#m2l5-api-key").value.trim();
      const statusEl = element.querySelector("#m2l5-key-status");
      if (!key) {
        statusEl.textContent = "Enter a key first.";
        statusEl.className = "m2l5-status error";
        return;
      }
      try {
        await activity.sendAction("credentials.save", { haiku_api_key: key });
        statusEl.textContent = "Saved.";
        statusEl.className = "m2l5-status success";
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m2l5-status error";
      }
    });
  }

  function renderViewView(state) {
    element.innerHTML = `
      ${STYLE}
      <div class="m2l5">
        <h3>Presentation Builder</h3>
        ${state.submitted
          ? `<p><strong>Topic:</strong> ${escapeHtml(state.topic)}</p>${renderGradeCard(state.grade_result)}`
          : `<p class="m2l5-locked">Not yet submitted.</p>`}
      </div>
    `;
  }

  function readDraftFromForm() {
    const topic = element.querySelector("#m2l5-topic").value;
    const stageEls = element.querySelectorAll(".m2l5-stage");
    const stages = [];
    stageEls.forEach((el) => {
      stages.push({
        label: el.querySelector(".m2l5-stage-label").value.trim(),
        text: el.querySelector(".m2l5-stage-text").value.trim(),
      });
    });
    const slideEls = element.querySelectorAll(".m2l5-slide");
    const slides = [];
    slideEls.forEach((el) => {
      const bulletsRaw = el.querySelector(".m2l5-slide-bullets").value;
      const bullets = bulletsRaw.split("\n").map((s) => s.trim()).filter(Boolean).slice(0, 3);
      slides.push({
        title: el.querySelector(".m2l5-slide-title").value.trim(),
        bullets: bullets,
        notes: el.querySelector(".m2l5-slide-notes").value.trim(),
      });
    });
    return { topic: topic, stages: stages, slides: slides };
  }

  function renderStagesHtml(stages) {
    return stages
      .map(
        (s, i) => `
        <div class="m2l5-stage">
          <div class="m2l5-stage-header">
            <input class="m2l5-stage-label" type="text" placeholder="Stage label (e.g. ${STAGE_LABEL_PLACEHOLDERS[i] || "Stage " + (i + 1)})" value="${escapeHtml(s.label)}" />
            ${stages.length > MIN_STAGES ? `<a href="#" class="m2l5-btn m2l5-btn-secondary m2l5-btn-small m2l5-remove-stage" data-index="${i}">Remove</a>` : ""}
          </div>
          <textarea class="m2l5-stage-text" placeholder="Full prompt text for this stage">${escapeHtml(s.text)}</textarea>
        </div>`
      )
      .join("");
  }

  function renderSlidesHtml(slides) {
    return slides
      .map(
        (s, i) => `
        <div class="m2l5-slide">
          <h4>Slide ${i + 1}</h4>
          <div class="m2l5-field">
            <label>Title</label>
            <input class="m2l5-slide-title" type="text" value="${escapeHtml(s.title)}" />
          </div>
          <div class="m2l5-field">
            <label>Bullets (one per line, max 3 — extra lines ignored)</label>
            <textarea class="m2l5-slide-bullets">${escapeHtml((s.bullets || []).filter(Boolean).join("\n"))}</textarea>
          </div>
          <div class="m2l5-field">
            <label>Speaker notes</label>
            <textarea class="m2l5-slide-notes">${escapeHtml(s.notes)}</textarea>
          </div>
        </div>`
      )
      .join("");
  }

  function wireStageButtons() {
    element.querySelectorAll(".m2l5-remove-stage").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        const draft = readDraftFromForm();
        draftStages = draft.stages;
        draftSlides = draft.slides;
        draftStages.splice(parseInt(btn.getAttribute("data-index"), 10), 1);
        rerenderForm();
      });
    });
    const addBtn = element.querySelector("#m2l5-add-stage");
    if (addBtn) {
      addBtn.addEventListener("click", (e) => {
        e.preventDefault();
        const draft = readDraftFromForm();
        draftStages = draft.stages;
        draftSlides = draft.slides;
        if (draftStages.length < MAX_STAGES) {
          draftStages.push({ label: "", text: "" });
        }
        rerenderForm();
      });
    }
  }

  function rerenderForm() {
    element.querySelector("#m2l5-stages-container").innerHTML = renderStagesHtml(draftStages);
    wireStageButtons();
  }

  function renderPlayView(state) {
    if (state.submitted) {
      element.innerHTML = `
        ${STYLE}
        <div class="m2l5">
          <h3>Presentation Builder</h3>
          <p class="m2l5-locked">Submitted — this activity is now locked.</p>
          <p><strong>Topic:</strong> ${escapeHtml(state.topic)}</p>
          ${renderGradeCard(state.grade_result)}
        </div>
      `;
      return;
    }

    draftStages = normalizeStages(state.prompt_stages);
    draftSlides = normalizeSlides(state.slides);
    const topic = state.topic || "";

    element.innerHTML = `
      ${STYLE}
      <div class="m2l5">
        <h3>Presentation Builder</h3>
        <p class="m2l5-hint">Pick an approved topic, submit at least 3 labeled staged prompts (outline, content, speaker notes, visual suggestions), then transcribe your final 5-slide deck below. Build the deck with your own AI tool of choice using these prompts, then bring the results here.</p>

        ${state.grade_result && typeof state.grade_result.weighted_total === "number" && !state.grade_result.passed
          ? `<div class="m2l5-section">
               <p class="m2l5-status error"><strong>Your last submission did not meet the passing threshold.</strong> Review the feedback below, revise your deck or prompts, and submit again.</p>
               ${renderGradeCard(state.grade_result)}
             </div>`
          : ""}

        <div class="m2l5-section">
          <div class="m2l5-field">
            <label for="m2l5-topic">Topic</label>
            <select id="m2l5-topic">
              <option value="">— select —</option>
              ${APPROVED_TOPICS.map((t) => `<option value="${escapeHtml(t)}" ${t === topic ? "selected" : ""}>${escapeHtml(t)}</option>`).join("")}
            </select>
          </div>
        </div>

        <div class="m2l5-section">
          <h3>Staged prompts</h3>
          <div id="m2l5-stages-container">${renderStagesHtml(draftStages)}</div>
          <a href="#" class="m2l5-btn m2l5-btn-secondary m2l5-btn-small" id="m2l5-add-stage">+ Add stage</a>
        </div>

        <div class="m2l5-section">
          <h3>Slides (exactly 5)</h3>
          ${renderSlidesHtml(draftSlides)}
        </div>

        <a href="#" class="m2l5-btn m2l5-btn-secondary" id="m2l5-save">
          <span class="m2l5-spinner" id="m2l5-save-spinner"></span>
          <span>Save draft</span>
        </a>
        <a href="#" class="m2l5-btn" id="m2l5-submit">
          <span class="m2l5-spinner" id="m2l5-submit-spinner"></span>
          <span>Submit for grading</span>
        </a>
        <div class="m2l5-status" id="m2l5-form-status"></div>
      </div>
    `;

    wireStageButtons();

    element.querySelector("#m2l5-save").addEventListener("click", async (e) => {
      e.preventDefault();
      const draft = readDraftFromForm();
      const statusEl = element.querySelector("#m2l5-form-status");
      const btn = element.querySelector("#m2l5-save");
      btn.classList.add("is-busy");
      try {
        await activity.sendAction("deck.save", {
          topic: draft.topic,
          prompt_stages: draft.stages,
          slides: draft.slides,
        });
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m2l5-status error";
      } finally {
        btn.classList.remove("is-busy");
      }
    });

    element.querySelector("#m2l5-submit").addEventListener("click", async (e) => {
      e.preventDefault();
      const draft = readDraftFromForm();
      const statusEl = element.querySelector("#m2l5-form-status");
      const btn = element.querySelector("#m2l5-submit");
      btn.setAttribute("disabled", "disabled");
      btn.classList.add("is-busy");
      statusEl.textContent = "Saving draft, then grading — this can take a few seconds…";
      statusEl.className = "m2l5-status";
      try {
        await activity.sendAction("deck.save", {
          topic: draft.topic,
          prompt_stages: draft.stages,
          slides: draft.slides,
        });
        await activity.sendAction("deck.submit", {});
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      } catch (err) {
        statusEl.textContent = "Submit failed: " + err;
        statusEl.className = "m2l5-status error";
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      }
    });
  }

  activity.onEvent = (name, value) => {
    if (name === "deck.saved") {
      activity.state.topic = value.topic;
      activity.state.prompt_stages = value.prompt_stages;
      activity.state.slides = value.slides;
      const statusEl = element.querySelector("#m2l5-form-status");
      if (statusEl) {
        statusEl.textContent = "Draft saved.";
        statusEl.className = "m2l5-status success";
      }
      return;
    } else if (name === "deck.graded") {
      activity.state.grade_result = value;
      activity.state.submitted = !!value.passed;
      render();
      return;
    } else if (name === "generation.error") {
      const statusEl = element.querySelector("#m2l5-form-status") || element.querySelector("#m2l5-key-status");
      if (statusEl) {
        statusEl.textContent = value;
        statusEl.className = "m2l5-status error";
      }
      const submitBtn = element.querySelector("#m2l5-submit");
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
