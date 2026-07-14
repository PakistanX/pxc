// UI for m2l6-visual-story.
// Edit mode: course staff configure the Anthropic API key.
// Play mode: student picks an approved topic, writes 3 image-generation
// prompts (each covering subject/style/composition/mood/context) with a
// consistent style anchor, writes 3 captions forming a narrative, saves the
// draft, then submits for automatic rubric grading. No image generation —
// grading is text-only (see sandbox.js's design note).
// View mode: read-only summary of the student's final submission + grade.

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const IMAGE_COUNT = 3;

const STYLE = `
<style>
  .m2l6 { font-family: sans-serif; max-width: 800px; color: #1d2029; }
  .m2l6 h3 { margin: 0 0 0.5rem; }
  .m2l6-section { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }
  .m2l6-field { margin-bottom: 0.75rem; }
  .m2l6-field label { display: block; font-weight: 600; margin-bottom: 0.25rem; }
  .m2l6-field select, .m2l6-field textarea, .m2l6-field input {
    width: 100%; padding: 0.5rem; box-sizing: border-box; font-family: inherit; font-size: 0.9rem;
    border: 1px solid #b0b6bf; border-radius: 4px;
  }
  .m2l6-field textarea { min-height: 90px; resize: vertical; }
  .m2l6-hint { font-size: 0.8rem; color: #6c7688; margin-top: 0.25rem; }
  .m2l6-btn {
    display: inline-flex; align-items: center; gap: 0.5rem;
    padding: 0.5rem 1.1rem; cursor: pointer; border: none; border-radius: 4px;
    background: #0075b4; color: #fff; font-size: 0.9rem; margin-right: 0.5rem;
  }
  .m2l6-btn:hover { background: #005f92; }
  .m2l6-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .m2l6-btn-secondary { background: #6c7688; }
  .m2l6-spinner {
    display: none; width: 12px; height: 12px; flex: 0 0 auto;
    border: 2px solid rgba(255, 255, 255, 0.4); border-top-color: #fff;
    border-radius: 50%; animation: m2l6-spin 0.7s linear infinite;
  }
  .m2l6-btn.is-busy .m2l6-spinner { display: inline-block; }
  @keyframes m2l6-spin { to { transform: rotate(360deg); } }
  .m2l6-status { margin-top: 0.5rem; font-size: 0.875rem; }
  .m2l6-status.error { color: #b52626; }
  .m2l6-status.success { color: #1b7a3d; }
  .m2l6-badge { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
  .m2l6-badge.configured { background: #d4edda; color: #155724; }
  .m2l6-badge.not-configured { background: #fff3cd; color: #856404; }
  .m2l6-image { border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.6rem; margin-bottom: 0.6rem; }
  .m2l6-image h4 { margin: 0 0 0.4rem; }
  .m2l6-grade-card { border: 1px solid #d0d5dd; border-radius: 6px; padding: 1rem; margin-top: 1rem; }
  .m2l6-grade-total { font-size: 1.8rem; font-weight: 700; }
  .m2l6-grade-letter { font-size: 1.1rem; font-weight: 700; padding: 0.1rem 0.6rem; border-radius: 4px; margin-left: 0.5rem; }
  .m2l6-grade-letter.A, .m2l6-grade-letter.B { background: #d4edda; color: #155724; }
  .m2l6-grade-letter.C { background: #fff3cd; color: #856404; }
  .m2l6-grade-letter.F { background: #f8d7da; color: #721c24; }
  .m2l6-criteria { display: flex; flex-wrap: wrap; gap: 0.75rem; margin: 0.75rem 0; }
  .m2l6-criterion { flex: 1 1 30%; border: 1px solid #e2e5e9; border-radius: 4px; padding: 0.5rem; text-align: center; }
  .m2l6-criterion .verdict { font-size: 1.3rem; font-weight: 700; }
  .m2l6-criterion .verdict.Y { color: #1b7a3d; }
  .m2l6-criterion .verdict.N { color: #b52626; }
  .m2l6-flags { color: #b52626; font-size: 0.85rem; }
  .m2l6-locked { color: #6c7688; font-style: italic; }
</style>
`;

const APPROVED_TOPICS = [
  "A day in the life of a future city",
  "The journey of a product from concept to customer",
  "A visual metaphor of a patient's visit to a healthcare clinic",
];

const CRITERIA_LABELS = [
  ["c1_image_count", "Image Count"],
  ["c2_prompt_elements", "Prompt Elements"],
  ["c3_style_anchor", "Style Anchor"],
  ["c4_caption_narrative", "Caption Narrative"],
  ["c5_topic_match", "Topic Match"],
  ["c6_submission_format", "Submission Format"],
];

function renderGradeCard(grade) {
  if (!grade || typeof grade.weighted_total !== "number") return "";
  const letter = escapeHtml(grade.letter_grade || "");
  const criteria = CRITERIA_LABELS.map(([key, label]) => {
    const verdict = escapeHtml((grade.criteria && grade.criteria[key]) || "?");
    return `<div class="m2l6-criterion"><div>${label}</div><div class="verdict ${verdict}">${verdict}</div></div>`;
  }).join("");
  const flags = Array.isArray(grade.flags) && grade.flags.length
    ? `<ul class="m2l6-flags">${grade.flags.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : "";
  return `
    <div class="m2l6-grade-card">
      <span class="m2l6-grade-total">${Math.round(grade.weighted_total * 10) / 10}%</span>
      <span class="m2l6-grade-letter ${letter}">${letter}</span>
      <div class="m2l6-criteria">${criteria}</div>
      <p>${escapeHtml(grade.feedback || "")}</p>
      ${flags}
      <p class="m2l6-hint">Passing threshold: 66.7% (4 of 6 criteria). Confidence: ${escapeHtml(grade.confidence || "n/a")}.</p>
    </div>
  `;
}

function normalizeImages(images) {
  const result = [];
  for (let i = 0; i < IMAGE_COUNT; i++) {
    const img = (images && images[i]) || {};
    result.push({ prompt: img.prompt || "", caption: img.caption || "" });
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
      <div class="m2l6">
        <div class="m2l6-section">
          <h3>AI API Key
            <span class="m2l6-badge ${configured ? "configured" : "not-configured"}">
              ${configured ? "Configured" : "Not configured"}
            </span>
          </h3>
          <p class="m2l6-hint">This activity calls Anthropic's Claude Haiku to grade submissions. Paste a valid Anthropic API key (starts with <code>sk-ant-</code>) here once per course — it's stored server-side and never shown again.</p>
          <div class="m2l6-field">
            <label for="m2l6-api-key">Anthropic API key</label>
            <input type="password" id="m2l6-api-key" placeholder="sk-ant-..." autocomplete="off" />
          </div>
          <a href="#" class="m2l6-btn" id="m2l6-save-key">Save key</a>
          <div class="m2l6-status" id="m2l6-key-status"></div>
        </div>
        <div class="m2l6-section">
          <h3>Preview</h3>
          <p class="m2l6-hint">Students pick one of three approved topics, write 3 image-generation prompts (each with subject, style, composition, mood/lighting, context/setting, sharing a consistent style anchor) and 3 captions forming a narrative, then submit for automatic rubric grading (6 binary criteria, ~16.7% each, 66.7% to pass). No images are generated or submitted — grading is text-only.</p>
        </div>
      </div>
    `;

    element.querySelector("#m2l6-save-key").addEventListener("click", async (e) => {
      e.preventDefault();
      const key = element.querySelector("#m2l6-api-key").value.trim();
      const statusEl = element.querySelector("#m2l6-key-status");
      if (!key) {
        statusEl.textContent = "Enter a key first.";
        statusEl.className = "m2l6-status error";
        return;
      }
      try {
        await activity.sendAction("credentials.save", { haiku_api_key: key });
        statusEl.textContent = "Saved.";
        statusEl.className = "m2l6-status success";
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m2l6-status error";
      }
    });
  }

  function renderViewView(state) {
    element.innerHTML = `
      ${STYLE}
      <div class="m2l6">
        <h3>Visual Story Collection</h3>
        ${state.submitted
          ? `<p><strong>Topic:</strong> ${escapeHtml(state.topic)}</p>${renderGradeCard(state.grade_result)}`
          : `<p class="m2l6-locked">Not yet submitted.</p>`}
      </div>
    `;
  }

  function readDraftFromForm() {
    const topic = element.querySelector("#m2l6-topic").value;
    const imageEls = element.querySelectorAll(".m2l6-image");
    const images = [];
    imageEls.forEach((el) => {
      images.push({
        prompt: el.querySelector(".m2l6-image-prompt").value.trim(),
        caption: el.querySelector(".m2l6-image-caption").value.trim(),
      });
    });
    return { topic: topic, images: images };
  }

  function renderImagesHtml(images) {
    return images
      .map(
        (img, i) => `
        <div class="m2l6-image">
          <h4>Image ${i + 1}</h4>
          <div class="m2l6-field">
            <label>Image-generation prompt (Subject, Style, Composition, Mood/Lighting, Context/Setting)</label>
            <textarea class="m2l6-image-prompt" placeholder="Subject: ... Style: ... Composition: ... Mood/Lighting: ... Context/Setting: ...">${escapeHtml(img.prompt)}</textarea>
          </div>
          <div class="m2l6-field">
            <label>Caption</label>
            <textarea class="m2l6-image-caption" placeholder="Caption text for this image">${escapeHtml(img.caption)}</textarea>
          </div>
        </div>`
      )
      .join("");
  }

  function renderPlayView(state) {
    if (state.submitted) {
      element.innerHTML = `
        ${STYLE}
        <div class="m2l6">
          <h3>Visual Story Collection</h3>
          <p class="m2l6-locked">Submitted — this activity is now locked.</p>
          <p><strong>Topic:</strong> ${escapeHtml(state.topic)}</p>
          ${renderGradeCard(state.grade_result)}
        </div>
      `;
      return;
    }

    const images = normalizeImages(state.images);
    const topic = state.topic || "";

    element.innerHTML = `
      ${STYLE}
      <div class="m2l6">
        <h3>Visual Story Collection</h3>
        <p class="m2l6-hint">Pick an approved topic, write 3 image-generation prompts sharing a consistent style anchor phrase, and 3 captions that read as one sequential story (beginning, middle, end). No images are needed — only your prompts and captions are graded.</p>

        <div class="m2l6-section">
          <div class="m2l6-field">
            <label for="m2l6-topic">Topic</label>
            <select id="m2l6-topic">
              <option value="">— select —</option>
              ${APPROVED_TOPICS.map((t) => `<option value="${escapeHtml(t)}" ${t === topic ? "selected" : ""}>${escapeHtml(t)}</option>`).join("")}
            </select>
          </div>
        </div>

        <div class="m2l6-section">
          <h3>Images (exactly 3)</h3>
          ${renderImagesHtml(images)}
        </div>

        <a href="#" class="m2l6-btn m2l6-btn-secondary" id="m2l6-save">
          <span class="m2l6-spinner" id="m2l6-save-spinner"></span>
          <span>Save draft</span>
        </a>
        <a href="#" class="m2l6-btn" id="m2l6-submit">
          <span class="m2l6-spinner" id="m2l6-submit-spinner"></span>
          <span>Submit for grading</span>
        </a>
        <div class="m2l6-status" id="m2l6-form-status"></div>
      </div>
    `;

    element.querySelector("#m2l6-save").addEventListener("click", async (e) => {
      e.preventDefault();
      const draft = readDraftFromForm();
      const statusEl = element.querySelector("#m2l6-form-status");
      const btn = element.querySelector("#m2l6-save");
      btn.classList.add("is-busy");
      try {
        await activity.sendAction("story.save", { topic: draft.topic, images: draft.images });
      } catch (err) {
        statusEl.textContent = "Save failed: " + err;
        statusEl.className = "m2l6-status error";
      } finally {
        btn.classList.remove("is-busy");
      }
    });

    element.querySelector("#m2l6-submit").addEventListener("click", async (e) => {
      e.preventDefault();
      const draft = readDraftFromForm();
      const statusEl = element.querySelector("#m2l6-form-status");
      const btn = element.querySelector("#m2l6-submit");
      btn.setAttribute("disabled", "disabled");
      btn.classList.add("is-busy");
      statusEl.textContent = "Saving draft, then grading — this can take a few seconds…";
      statusEl.className = "m2l6-status";
      try {
        await activity.sendAction("story.save", { topic: draft.topic, images: draft.images });
        await activity.sendAction("story.submit", {});
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      } catch (err) {
        statusEl.textContent = "Submit failed: " + err;
        statusEl.className = "m2l6-status error";
        btn.removeAttribute("disabled");
        btn.classList.remove("is-busy");
      }
    });
  }

  activity.onEvent = (name, value) => {
    if (name === "story.saved") {
      activity.state.topic = value.topic;
      activity.state.images = value.images;
      const statusEl = element.querySelector("#m2l6-form-status");
      if (statusEl) {
        statusEl.textContent = "Draft saved.";
        statusEl.className = "m2l6-status success";
      }
      return;
    } else if (name === "story.graded") {
      activity.state.grade_result = value;
      activity.state.submitted = true;
      render();
      return;
    } else if (name === "generation.error") {
      const statusEl = element.querySelector("#m2l6-form-status") || element.querySelector("#m2l6-key-status");
      if (statusEl) {
        statusEl.textContent = value;
        statusEl.className = "m2l6-status error";
      }
      const submitBtn = element.querySelector("#m2l6-submit");
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
