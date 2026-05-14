import { Renderer, Stave, StaveNote, Voice, Formatter, Accidental } from "vexflow";

const SCALES = {
  major:            { name: "Major (Ionian)",         vexKeys: ["c/4","d/4","e/4","f/4","g/4","a/4","b/4","c/5"],          displayNames: ["C","D","E","F","G","A","B","C"] },
  natural_minor:    { name: "Natural Minor (Aeolian)", vexKeys: ["c/4","d/4","eb/4","f/4","g/4","ab/4","bb/4","c/5"],       displayNames: ["C","D","Eb","F","G","Ab","Bb","C"] },
  harmonic_minor:   { name: "Harmonic Minor",          vexKeys: ["c/4","d/4","eb/4","f/4","g/4","ab/4","b/4","c/5"],        displayNames: ["C","D","Eb","F","G","Ab","B","C"] },
  melodic_minor:    { name: "Melodic Minor",           vexKeys: ["c/4","d/4","eb/4","f/4","g/4","a/4","b/4","c/5"],         displayNames: ["C","D","Eb","F","G","A","B","C"] },
  dorian:           { name: "Dorian",                  vexKeys: ["c/4","d/4","eb/4","f/4","g/4","a/4","bb/4","c/5"],        displayNames: ["C","D","Eb","F","G","A","Bb","C"] },
  phrygian:         { name: "Phrygian",                vexKeys: ["c/4","db/4","eb/4","f/4","g/4","ab/4","bb/4","c/5"],      displayNames: ["C","Db","Eb","F","G","Ab","Bb","C"] },
  lydian:           { name: "Lydian",                  vexKeys: ["c/4","d/4","e/4","f#/4","g/4","a/4","b/4","c/5"],         displayNames: ["C","D","E","F#","G","A","B","C"] },
  mixolydian:       { name: "Mixolydian",              vexKeys: ["c/4","d/4","e/4","f/4","g/4","a/4","bb/4","c/5"],         displayNames: ["C","D","E","F","G","A","Bb","C"] },
  pentatonic_major: { name: "Pentatonic Major",        vexKeys: ["c/4","d/4","e/4","g/4","a/4","c/5"],                      displayNames: ["C","D","E","G","A","C"] },
  pentatonic_minor: { name: "Pentatonic Minor",        vexKeys: ["c/4","eb/4","f/4","g/4","bb/4","c/5"],                    displayNames: ["C","Eb","F","G","Bb","C"] },
  blues:            { name: "Blues",                   vexKeys: ["c/4","eb/4","f/4","f#/4","g/4","bb/4","c/5"],             displayNames: ["C","Eb","F","F#","G","Bb","C"] },
};

const C4_FREQ = 261.63;
// Semitone offsets matching vexKeys order per scale (used for audio)
const SCALE_SEMITONES = {
  major:            [0,2,4,5,7,9,11,12],
  natural_minor:    [0,2,3,5,7,8,10,12],
  harmonic_minor:   [0,2,3,5,7,8,11,12],
  melodic_minor:    [0,2,3,5,7,9,11,12],
  dorian:           [0,2,3,5,7,9,10,12],
  phrygian:         [0,1,3,5,7,8,10,12],
  lydian:           [0,2,4,6,7,9,11,12],
  mixolydian:       [0,2,4,5,7,9,10,12],
  pentatonic_major: [0,2,4,7,9,12],
  pentatonic_minor: [0,3,5,7,10,12],
  blues:            [0,3,5,6,7,10,12],
};

function noteFreq(semitones) {
  return C4_FREQ * Math.pow(2, semitones / 12);
}

function getAccidental(key) {
  const note = key.split("/")[0];
  if (note.includes("#")) return "#";
  if (note.length > 1 && note[1] === "b") return "b";
  return null;
}

function playTone(freq, audioCtx) {
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.type = "sine";
  osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
  gain.gain.setValueAtTime(0.4, audioCtx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 1.0);
  osc.start(audioCtx.currentTime);
  osc.stop(audioCtx.currentTime + 1.0);
}

function renderStaff(containerEl, vexKeys, activeIndex) {
  const existing = containerEl.querySelector("svg");
  if (existing) existing.remove(); else containerEl.innerHTML = "";
  const noteCount = vexKeys.length;
  const width = Math.max(400, noteCount * 58 + 100);
  const renderer = new Renderer(containerEl, Renderer.Backends.SVG);
  renderer.resize(width, 150);
  const ctx = renderer.getContext();
  const stave = new Stave(10, 30, width - 20);
  stave.addClef("treble");
  stave.setContext(ctx).draw();
  const notes = vexKeys.map((key, i) => {
    const n = new StaveNote({ keys: [key], duration: "q" });
    const acc = getAccidental(key);
    if (acc) n.addModifier(new Accidental(acc), 0);
    if (i === activeIndex) n.setStyle({ fillStyle: "#e67e22", strokeStyle: "#e67e22" });
    return n;
  });
  const voice = new Voice({ num_beats: noteCount, beat_value: 4 }).setMode(Voice.Mode.SOFT);
  voice.addTickables(notes);
  new Formatter().joinVoices([voice]).format([voice], width - 70);
  voice.draw(ctx, stave);
  return notes.map(n => n.getAbsoluteX());
}

export function setup(activity) {
  const el = activity.element;
  let audioCtx = null;
  let keydownHandler = null;
  let rootEl = null;

  function getAudio() {
    if (!audioCtx) audioCtx = new AudioContext();
    return audioCtx;
  }

  activity.onEvent = (name, value) => {
    if (name === "fields.change.scale") {
      activity.state.scale = value;
      if (activity.permission !== "edit") renderPlay();
    }
  };

  if (activity.permission === "edit") {
    renderEdit();
  } else {
    renderPlay();
  }

  function renderEdit() {
    const current = activity.state.scale || "major";
    const options = Object.entries(SCALES)
      .map(([key, { name }]) =>
        `<option value="${key}"${key === current ? " selected" : ""}>${name}</option>`
      )
      .join("");

    el.innerHTML = `
      <style>
        .h-edit { font-family: sans-serif; padding: 24px; max-width: 520px; }
        .h-edit h2 { margin: 0 0 20px; color: #222; font-size: 20px; }
        .h-edit label { display: block; margin-bottom: 6px; font-weight: 600; color: #444; font-size: 14px; }
        .h-edit select { width: 100%; padding: 10px; font-size: 15px; border: 1px solid #ccc; border-radius: 6px; background: #fff; }
        .h-edit .preview { margin-top: 18px; padding: 14px; background: #f7f8fa; border-radius: 8px; overflow-x: auto; }
        .h-edit .preview-label { font-size: 12px; color: #888; margin-bottom: 10px; font-weight: 600; letter-spacing: 0.5px; text-transform: uppercase; }
        .h-edit button { margin-top: 20px; padding: 10px 28px; background: #4a90d9; color: #fff; border: none; border-radius: 6px; font-size: 15px; cursor: pointer; font-weight: 600; }
        .h-edit button:hover { background: #357abd; }
      </style>
      <div class="h-edit">
        <h2>Configure Scale</h2>
        <label for="scale-sel">Scale</label>
        <select id="scale-sel">${options}</select>
        <div class="preview">
          <div class="preview-label">Notes in C</div>
          <div id="staff-preview"></div>
        </div>
        <button id="save-btn">Save</button>
      </div>
    `;

    function updatePreview(key) {
      renderStaff(el.querySelector("#staff-preview"), SCALES[key].vexKeys, -1);
    }

    const sel = el.querySelector("#scale-sel");
    updatePreview(current);
    sel.addEventListener("change", () => updatePreview(sel.value));
    el.querySelector("#save-btn").addEventListener("click", () => {
      activity.sendAction("config.save", { scale: sel.value });
    });
  }

  function renderPlay() {
    if (keydownHandler && rootEl) {
      rootEl.removeEventListener("keydown", keydownHandler);
      keydownHandler = null;
    }

    const scaleKey = activity.state.scale || "major";
    const scale = SCALES[scaleKey];
    const semitones = SCALE_SEMITONES[scaleKey];
    const n = scale.vexKeys.length;

    el.innerHTML = `
      <style>
        .h-play { font-family: sans-serif; padding: 24px; outline: none; }
        .h-play h2 { margin: 0 0 4px; color: #222; font-size: 20px; }
        .h-play .sub { color: #888; font-size: 13px; margin-bottom: 16px; }
        #staff { position: relative; min-height: 210px; overflow-x: auto; background: #fff; border-radius: 8px; }
        .chip { position: absolute; display: flex; flex-direction: column; align-items: center; width: 44px; padding: 6px 4px; background: #4a90d9; color: #fff; border-radius: 8px; cursor: pointer; transition: background 0.1s, transform 0.08s; font-size: 16px; font-weight: 700; }
        .chip span { font-size: 11px; font-weight: 400; margin-top: 2px; opacity: 0.9; }
        .chip.active { background: #e67e22; transform: scale(1.1); }
        .hint { margin-top: 14px; color: #bbb; font-size: 12px; }
      </style>
      <div class="h-play" tabindex="-1">
        <h2>${scale.name}</h2>
        <p class="sub">Press 1–${n} or click to play notes</p>
        <div id="staff"></div>
        <p class="hint">All notes in C &nbsp;·&nbsp; keys 1–${n}</p>
      </div>
    `;

    const staffEl = el.querySelector("#staff");
    const xPositions = renderStaff(staffEl, scale.vexKeys, -1);

    scale.displayNames.forEach((name, i) => {
      const chip = el.ownerDocument.createElement("div");
      chip.className = "chip";
      chip.dataset.idx = String(i);
      chip.innerHTML = `${i + 1}<span>${name}</span>`;
      chip.style.left = `${xPositions[i] - 22}px`;
      chip.style.top = "158px";
      chip.addEventListener("click", () => trigger(i));
      staffEl.appendChild(chip);
    });

    let activeTimeout = null;

    function trigger(idx) {
      playTone(noteFreq(semitones[idx]), getAudio());
      renderStaff(staffEl, scale.vexKeys, idx);
      staffEl.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      staffEl.querySelector(`.chip[data-idx="${idx}"]`).classList.add("active");
      if (activeTimeout) clearTimeout(activeTimeout);
      activeTimeout = setTimeout(() => {
        renderStaff(staffEl, scale.vexKeys, -1);
        staffEl.querySelectorAll(".chip").forEach(c => c.classList.remove("active"));
      }, 600);
    }

    rootEl = el.querySelector(".h-play");
    rootEl.addEventListener("mousedown", () => rootEl.focus());
    keydownHandler = (e) => {
      const num = parseInt(e.key);
      if (num >= 1 && num <= n) {
        e.preventDefault();
        trigger(num - 1);
      }
    };
    rootEl.addEventListener("keydown", keydownHandler);
    rootEl.focus();
  }
}
