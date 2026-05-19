// Activity script for Slideshow (reveal.js presentation)
// Embeds reveal.js in iframes for complete CSS/JS isolation.

const DEFAULT_SLIDES = `<section>
  <h2>Welcome</h2>
  <p>Edit this presentation in author mode.</p>
</section>
<section>
  <h2>Slide 2</h2>
  <p>Add more &lt;section&gt; elements for additional slides.</p>
</section>`;

const MEDIA_TOKEN_RE = /media:\/\/([A-Za-z0-9._-]+)/g;

function rewriteMediaTokens(html, files) {
  const urlByName = new Map((files || []).map((f) => [f.filename, f.url]));
  return html.replace(MEDIA_TOKEN_RE, (match, filename) =>
    urlByName.has(filename) ? urlByName.get(filename) : match
  );
}

function buildSrcdoc(slidesHtml, assetUrls, files) {
  const rewritten = rewriteMediaTokens(slidesHtml, files);
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <link rel="stylesheet" href="${assetUrls.resetCss}">
  <link rel="stylesheet" href="${assetUrls.revealCss}">
  <link rel="stylesheet" href="${assetUrls.themeCss}">
  <style>
    :root {
      --r-heading-font: Montserrat;
      --r-heading-text-transform: none;
      --r-heading-font-weight: normal;
      --r-main-font: "Open Sans";
    }
    body { margin: 0; }
  </style>
</head>
<body>
  <div class="reveal"><div class="slides">${rewritten}</div></div>
  <script src="${assetUrls.revealJs}"></script>
  <script>
    let deck = new Reveal(document.querySelector('.reveal'), {
      keyboardCondition: 'focused',
      transition: 'fade',
      progress: false,
      controls: false,
    });
    deck.initialize();
  </script>
</body>
</html>`;
}

export function setup(activity) {
  const element = activity.element;
  const permission = activity.permission;
  const assetUrls = {
    resetCss: activity.getAssetUrl("assets/reveal/reset.css"),
    revealCss: activity.getAssetUrl("assets/reveal/reveal.css"),
    themeCss: activity.getAssetUrl("assets/reveal/theme/white.css"),
    revealJs: activity.getAssetUrl("assets/reveal/reveal.js"),
  };

  function getSlidesHtml() {
    return activity.state.slides_html || "";
  }

  function getFiles() {
    return activity.state.files || [];
  }

  activity.onEvent = (name, value) => {
    if (name === "fields.change.slides_html") {
      activity.state.slides_html = value;
      if (permission !== "edit") {
        renderPlayView();
      }
    } else if (name === "files.changed") {
      activity.state.files = value;
      if (permission === "edit") {
        renderFileList();
        updatePreview(element.querySelector("#slides-input")?.value ?? getSlidesHtml());
      } else {
        renderPlayView();
      }
    }
  };

  function render() {
    if (permission === "edit") {
      renderEditView();
    } else {
      renderPlayView();
    }
  }

  function renderEditView() {
    const slidesHtml = getSlidesHtml() || DEFAULT_SLIDES;

    element.innerHTML = `
      <style>
        .slideshow-container { font-family: sans-serif; max-width: 900px; }
        .slides-editor { width: 100%; min-height: 300px; font-family: monospace; font-size: 0.9rem; padding: 0.5rem; box-sizing: border-box; tab-size: 2; }
        .save-btn { margin-top: 0.5rem; padding: 0.5rem 1rem; cursor: pointer; }
        .feedback { margin-top: 0.5rem; padding: 0.5rem; border-radius: 4px; }
        .feedback.success { background: #d4edda; color: #155724; }
        .feedback.error { background: #f8d7da; color: #721c24; }
        .preview-label { font-weight: bold; margin-top: 1rem; }
        .slideshow-preview { margin-top: 0.5rem; }
        .media-panel { border: 1px solid #ddd; border-radius: 4px; padding: 0.75rem; margin-bottom: 1rem; background: #fafafa; }
        .media-panel h3 { margin-top: 0; }
        .media-upload-status { color: #666; font-size: 0.85rem; margin-top: 0.25rem; min-height: 1em; }
        .media-list { list-style: none; padding: 0; margin: 0.5rem 0 0 0; }
        .media-list li { display: flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0; border-top: 1px solid #eee; }
        .media-list li:first-child { border-top: none; }
        .media-name { font-weight: 600; min-width: 12rem; }
        .media-token { font-family: monospace; font-size: 0.85rem; background: #fff; padding: 0.1rem 0.35rem; border: 1px solid #ddd; border-radius: 3px; }
        .media-btn { padding: 0.2rem 0.5rem; cursor: pointer; font-size: 0.8rem; }
        .media-empty { color: #666; font-style: italic; font-size: 0.9rem; }
        .editor-hint { color: #666; font-size: 0.8rem; margin-top: 0.25rem; }
      </style>
      <div class="slideshow-container">
        <div class="media-panel">
          <h3>Media files</h3>
          <input type="file" id="media-input" multiple>
          <div class="media-upload-status" id="media-upload-status"></div>
          <div id="media-list-wrap"></div>
        </div>
        <h3>Edit Slides</h3>
        <p style="color: #666; font-size: 0.85rem;">
          Each slide is a <code>&lt;section&gt;</code> element. Nest <code>&lt;section&gt;</code> elements for vertical slides.
        </p>
        <textarea class="slides-editor" id="slides-input">${escapeHtml(slidesHtml)}</textarea>
        <div class="editor-hint">Reference uploaded files as <code>media://filename.ext</code> in your slide HTML.</div>
        <button type="button" class="save-btn" id="save-btn">Save</button>
        <div id="save-feedback"></div>
        <div class="preview-label">Preview:</div>
        <div class="slideshow-preview" id="slideshow-preview"></div>
      </div>
    `;

    element.querySelector("#media-input").addEventListener("change", onMediaFilesSelected);

    element.querySelector("#save-btn").addEventListener("click", async () => {
      const content = element.querySelector("#slides-input").value;
      const feedbackEl = element.querySelector("#save-feedback");
      try {
        await activity.sendAction("config.save", { slides_html: content });
        feedbackEl.innerHTML = '<div class="feedback success">Saved!</div>';
        updatePreview(content);
      } catch (err) {
        feedbackEl.innerHTML = '<div class="feedback error">Error: ' + escapeHtml(err.message) + '</div>';
      }
    });

    renderFileList();
    updatePreview(slidesHtml);
  }

  function renderFileList() {
    const wrap = element.querySelector("#media-list-wrap");
    if (!wrap) return;
    const files = getFiles();
    if (files.length === 0) {
      wrap.innerHTML = '<p class="media-empty">No files uploaded yet.</p>';
      return;
    }
    const rows = files
      .map(
        (f) => `
          <li data-filename="${escapeHtml(f.filename)}">
            <span class="media-name">${escapeHtml(f.filename)}</span>
            <code class="media-token">media://${escapeHtml(f.filename)}</code>
            <button type="button" class="media-btn copy-btn">Copy</button>
            <button type="button" class="media-btn delete-btn">Delete</button>
          </li>`
      )
      .join("");
    wrap.innerHTML = `<ul class="media-list">${rows}</ul>`;

    wrap.querySelectorAll(".media-list li").forEach((li) => {
      const filename = li.dataset.filename;
      li.querySelector(".copy-btn").addEventListener("click", () => {
        const text = "media://" + filename;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(text);
        }
      });
      li.querySelector(".delete-btn").addEventListener("click", () => {
        activity.sendAction("file.delete", { filename });
      });
    });
  }

  async function onMediaFilesSelected(e) {
    const status = element.querySelector("#media-upload-status");
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      status.textContent = `Uploading ${i + 1}/${files.length}: ${file.name}…`;
      try {
        const dataUri = await readFileAsDataUrl(file);
        await activity.sendAction("file.upload", { filename: file.name, data: dataUri });
      } catch (err) {
        status.textContent = `Error uploading ${file.name}: ${err.message}`;
        e.target.value = "";
        return;
      }
    }
    status.textContent = `Uploaded ${files.length} file${files.length === 1 ? "" : "s"}.`;
    e.target.value = "";
  }

  function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("FileReader failed"));
      reader.readAsDataURL(file);
    });
  }

  function updatePreview(slidesHtml) {
    const container = element.querySelector("#slideshow-preview");
    if (!container) return;
    if (!slidesHtml) {
      container.innerHTML = '<p style="color: #666; font-style: italic;">No slides to preview.</p>';
      return;
    }
    container.innerHTML = '<iframe style="width: 100%; height: 400px; border: 1px solid #ccc;"></iframe>';
    container.querySelector("iframe").srcdoc = buildSrcdoc(slidesHtml, assetUrls, getFiles());
  }

  function renderPlayView() {
    const slidesHtml = getSlidesHtml();

    element.innerHTML = `
      <style>
        .slideshow-container { font-family: sans-serif; }
        .no-slides { color: #666; font-style: italic; padding: 2rem; text-align: center; }
      </style>
      <div class="slideshow-container">
        ${slidesHtml
          ? '<iframe style="width: 100%; height: 500px; border: none;"></iframe>'
          : '<p class="no-slides">No slides configured yet.</p>'}
      </div>
    `;

    if (slidesHtml) {
      element.querySelector("iframe").srcdoc = buildSrcdoc(slidesHtml, assetUrls, getFiles());
    }
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  render();
}
