// m2l5-presentation-builder — practice decomposing a presentation build into
// staged prompts (outline/content/notes/visuals) and assembling a 5-slide
// deck with a narrative arc, graded automatically by an LLM against the
// M2L5 binary checklist rubric (6 criteria, ~16.7% weight each).
//
// Design note: students actually run their staged prompts with whatever AI
// tool they use (this activity doesn't call an LLM to build slide content —
// the point being graded is the *prompts*, not generating a deck in-tool).
// They transcribe the resulting topic/prompts/slide text into this form,
// which is exactly the structured text a real submission's markitdown-
// extracted .pptx would produce, then submit that for rubric grading. No
// in-app "generate slides" step, unlike the email/meeting activities.
//
// Actions:
// - credentials.save: store the course's Anthropic API key (edit only)
// - deck.save: validate + persist the draft (topic, staged prompts, slides)
// - deck.submit: re-validate the persisted draft, send it to Claude Haiku
//   for rubric grading, record the grade via reportScored, lock

import { httpRequest } from "pxc:sandbox/http";
import { reportCompleted, reportScored } from "pxc:sandbox/grading";
import { getField, setField, sendEvent } from "pxc:sandbox/state";

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_MODEL = "claude-haiku-4-5-20251001";
const ANTHROPIC_VERSION = "2023-06-01";
const MIN_PROMPT_STAGES = 3;
const MAX_PROMPT_STAGES = 6;
const REQUIRED_SLIDE_COUNT = 5;

const APPROVED_TOPICS = [
  "Smart Cities and the Future of Urban Living",
  "How Social Media Shapes Human Behavior",
  "AI in Education: Benefits, Risks, and Possibilities",
  "Climate Change Solutions That Can Work Now",
  "Work and Careers in the Age of Automation",
  "The Psychology of Consumer Decisions",
];

const GRADING_SYSTEM_PROMPT =
  "Grade student prompt engineering submissions against a binary checklist. Each criterion is " +
  "Y (pass) or N (fail). Output valid JSON only — no preamble, no markdown fences.";

function gradingRubricPrompt(submission) {
  return (
    "Grade this M2L5 submission: a set of prompts used to build a 5-slide AI-assisted presentation, " +
    "plus the extracted text of the slide deck. Apply each criterion strictly and independently.\n\n" +

    "CRITERIA (each is Y or N)\n\n" +

    "C1. Slide Count\n" +
    "Y — Exactly 5 slides present, each with a title and at least some speaker notes.\n" +
    "N — Fewer or more than 5 slides, or any slide is missing a title or speaker notes entirely.\n\n" +

    "C2. Narrative Structure\n" +
    "Y — Slides follow a coherent logical arc (e.g., title → problem → evidence → solution → call " +
    "to action, or equivalent progression). Slide titles alone are sufficient to confirm this.\n" +
    "N — Slides are disconnected, repetitive, or lack any discernible progression.\n\n" +

    "C3. Technique Usage\n" +
    "Y — At least 3 distinct CAR techniques are visibly present in the submitted prompts. Accepted " +
    "techniques: Role Assignment (named persona), Context & Constraints (audience/tone/scope " +
    "specified), Format & Success Criteria (word count, structure, visual guidance), Task " +
    "Decomposition (separate prompt per stage), Chain-of-Thought (reasoning about narrative or " +
    "message flow), Few-Shot Learning (example slide or note format provided).\n" +
    "N — Fewer than 3 distinct techniques identifiable in the prompt text.\n\n" +

    "C4. Prompt Stages\n" +
    "Y — At least 3 separate, labeled prompts submitted covering distinct stages (e.g., outline, " +
    "content, speaker notes, visual suggestions). A single mega-prompt that does everything at once " +
    "does not qualify.\n" +
    "N — Fewer than 3 separate prompts, or all stages collapsed into one prompt.\n\n" +

    "C5. Slide Text Quality\n" +
    "Y — Every slide has ≤3 key points or bullet items; no slide contains full prose paragraphs as " +
    "body text.\n" +
    "N — Any slide has >3 bullet points or uses full paragraphs as body text.\n\n" +

    "C6. Topic Validity\n" +
    "Y — Presentation is on one of the six approved topics: (1) Smart Cities and the Future of Urban " +
    "Living, (2) How Social Media Shapes Human Behavior, (3) AI in Education: Benefits, Risks, and " +
    "Possibilities, (4) Climate Change Solutions That Can Work Now, (5) Work and Careers in the Age " +
    "of Automation, (6) The Psychology of Consumer Decisions.\n" +
    "N — Topic does not match any of the six approved options.\n\n" +

    "SCORING\n" +
    "Each Y = 1 point. Total score = number of Y verdicts out of 6.\n" +
    "Weighted total (out of 100) = (Y_count / 6) × 100, rounded to one decimal.\n" +
    "Grade: 85–100=A (≥5 Y), 70–84=B (≥4.2 Y), 55–69=C (≥3.3 Y), <55=F (≤3 Y).\n" +
    "In practice: 6/6=100 A, 5/6=83.3 B, 4/6=66.7 C, 3/6=50 F, 2/6=33.3 F, 1/6=16.7 F. Do not " +
    "compute or include y_count/weighted_total/letter_grade yourself — those are derived from your " +
    "criteria verdicts separately.\n\n" +

    "Return ONLY this JSON:\n\n" +
    "{\n" +
    '  "criteria": {\n' +
    '    "c1_slide_count": "<Y/N>",\n' +
    '    "c2_narrative_structure": "<Y/N>",\n' +
    '    "c3_technique_usage": "<Y/N>",\n' +
    '    "c4_prompt_stages": "<Y/N>",\n' +
    '    "c5_slide_text_quality": "<Y/N>",\n' +
    '    "c6_topic_validity": "<Y/N>"\n' +
    "  },\n" +
    '  "feedback": "<2-3 sentences: note which criteria passed/failed and the single most impactful fix>",\n' +
    '  "confidence": "<HIGH/MEDIUM/LOW>",\n' +
    '  "flags": [<strings or empty array>]\n' +
    "}\n\n" +
    "SUBMISSION:\n\n" +
    submission
  );
}

function callAnthropic(apiKey, systemPrompt, userMessage, maxTokens) {
  const headers = [
    ["x-api-key", apiKey],
    ["anthropic-version", ANTHROPIC_VERSION],
    ["content-type", "application/json"],
  ];
  const body = JSON.stringify({
    model: ANTHROPIC_MODEL,
    max_tokens: maxTokens,
    system: systemPrompt,
    messages: [{ role: "user", content: userMessage }],
  });

  let raw;
  try {
    raw = httpRequest(ANTHROPIC_URL, "POST", body, headers);
  } catch (e) {
    throw new Error("Could not reach the AI service: " + (e && e.message ? e.message : String(e)));
  }

  const response = JSON.parse(raw);
  if (response.status !== 200) {
    let detail = response.body;
    try {
      detail = JSON.parse(response.body).error.message;
    } catch (e) {
      // leave detail as raw body
    }
    throw new Error("AI service returned HTTP " + response.status + ": " + detail);
  }

  const data = JSON.parse(response.body);
  if (!data.content || !data.content[0] || typeof data.content[0].text !== "string") {
    throw new Error("AI service returned an unexpected response shape.");
  }
  return data.content
    .filter((block) => block.type === "text")
    .map((block) => block.text)
    .join("\n")
    .trim();
}

function stripJsonFences(text) {
  const trimmed = text.trim();
  const fenced = trimmed.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return fenced ? fenced[1] : trimmed;
}

// The LLM grader is asked for both per-criterion Y/N verdicts AND a
// weighted total/letter grade computed from them — but it's a language
// model, not a calculator, and can get that arithmetic slightly wrong.
// Recompute both deterministically from the raw Y/N verdicts instead of
// trusting the model's own sum, matching the rubric's "in practice" table
// exactly (6/6=100 A, 5/6=83.3 B, 4/6=66.7 C, <=3/6=F).
const CRITERIA_KEYS = [
  "c1_slide_count",
  "c2_narrative_structure",
  "c3_technique_usage",
  "c4_prompt_stages",
  "c5_slide_text_quality",
  "c6_topic_validity",
];

function recomputeGrade(grade) {
  const yCount = CRITERIA_KEYS.filter((k) => grade.criteria[k] === "Y").length;
  let letter;
  if (yCount === 6) letter = "A";
  else if (yCount === 5) letter = "B";
  else if (yCount === 4) letter = "C";
  else letter = "F";
  grade.y_count = yCount;
  grade.weighted_total = Math.round((yCount / 6) * 1000) / 10;
  grade.letter_grade = letter;
  return grade;
}

function fail(message, userId) {
  sendEvent("generation.error", JSON.stringify(message), { userId: userId }, "play");
  return "";
}

// Structural-only validation — deliberately does NOT check technique count,
// narrative quality, bullet-count compliance, etc. Those are the LLM
// grader's job (C2/C3/C5); this just prevents an obviously incomplete draft
// from wasting an API call.
function validateDraft(topic, promptStages, slides) {
  if (!APPROVED_TOPICS.includes(topic)) {
    return "Choose one of the six approved topics.";
  }
  if (!Array.isArray(promptStages) || promptStages.length < MIN_PROMPT_STAGES) {
    return "Add at least " + MIN_PROMPT_STAGES + " separate, labeled prompt stages.";
  }
  for (const stage of promptStages) {
    if (!stage.label || !stage.label.trim() || !stage.text || !stage.text.trim()) {
      return "Every prompt stage needs a label and prompt text.";
    }
  }
  if (!Array.isArray(slides) || slides.length !== REQUIRED_SLIDE_COUNT) {
    return "Your deck must have exactly " + REQUIRED_SLIDE_COUNT + " slides.";
  }
  for (let i = 0; i < slides.length; i++) {
    if (!slides[i].title || !slides[i].title.trim()) {
      return "Slide " + (i + 1) + " needs a title.";
    }
  }
  return null;
}

function buildSubmissionText(topic, promptStages, slides) {
  const promptsText = promptStages
    .map((s) => s.label + ": " + s.text)
    .join("\n\n");
  const slidesText = slides
    .map((s, i) => {
      const bullets = Array.isArray(s.bullets) ? s.bullets.filter(Boolean).join("; ") : "";
      return "Slide " + (i + 1) + " — " + s.title + ": " + bullets + " | Speaker notes: " + (s.notes || "");
    })
    .join("\n\n");
  return "TOPIC: " + topic + "\n\nPROMPTS:\n\n" + promptsText + "\n\nSLIDES:\n\n" + slidesText;
}

export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  const userId = context.userId;

  if (name === "credentials.save") {
    if (permission !== "edit") {
      return fail("Only course staff can configure the API key.", userId);
    }
    setField("haiku_api_key", JSON.stringify(value.haiku_api_key || ""));
    sendEvent(
      "credentials.status",
      JSON.stringify({ configured: !!value.haiku_api_key }),
      null,
      "edit"
    );
    return "";
  }

  if (permission === "view") {
    return fail("This activity is read-only in this context.", userId);
  }

  const submitted = JSON.parse(getField("submitted"));
  if (submitted && (name === "deck.save" || name === "deck.submit")) {
    return fail("This activity has already been submitted — submissions are final.", userId);
  }

  if (name === "deck.save") {
    const topic = value.topic || "";
    const promptStages = (value.prompt_stages || []).slice(0, MAX_PROMPT_STAGES);
    const slides = value.slides || [];

    const error = validateDraft(topic, promptStages, slides);
    if (error) {
      return fail(error, userId);
    }

    setField("topic", JSON.stringify(topic));
    setField("prompt_stages", JSON.stringify(promptStages));
    setField("slides", JSON.stringify(slides));

    sendEvent(
      "deck.saved",
      JSON.stringify({ topic: topic, prompt_stages: promptStages, slides: slides }),
      { userId: userId },
      "play"
    );
    return "";
  }

  if (name === "deck.submit") {
    const topic = JSON.parse(getField("topic"));
    const promptStages = JSON.parse(getField("prompt_stages"));
    const slides = JSON.parse(getField("slides"));

    const error = validateDraft(topic, promptStages, slides);
    if (error) {
      return fail("Save a complete draft first: " + error, userId);
    }
    const apiKey = JSON.parse(getField("haiku_api_key"));
    if (!apiKey) {
      return fail("This activity's AI key isn't configured yet — ask course staff.", userId);
    }

    const submission = buildSubmissionText(topic, promptStages, slides);

    let gradeJsonText;
    try {
      gradeJsonText = callAnthropic(apiKey, GRADING_SYSTEM_PROMPT, gradingRubricPrompt(submission), 500);
    } catch (e) {
      return fail("Grading failed: " + e.message, userId);
    }

    let grade;
    try {
      grade = JSON.parse(stripJsonFences(gradeJsonText));
    } catch (e) {
      return fail("Grading response was not valid JSON: " + gradeJsonText.slice(0, 200), userId);
    }
    if (
      !grade ||
      !grade.criteria ||
      !CRITERIA_KEYS.every((k) => grade.criteria[k] === "Y" || grade.criteria[k] === "N")
    ) {
      return fail("Grading response was missing required fields.", userId);
    }
    grade = recomputeGrade(grade);

    setField("grade_result", JSON.stringify(grade));
    setField("submitted", JSON.stringify(true));

    reportScored(Math.max(0, Math.min(1, grade.weighted_total / 100)));
    reportCompleted();

    sendEvent("deck.graded", JSON.stringify(grade), { userId: userId }, "play");
    return "";
  }

  return fail("Unknown action.", userId);
}

export function getState(context, permission) {
  const state = {
    topic: JSON.parse(getField("topic")),
    prompt_stages: JSON.parse(getField("prompt_stages")),
    slides: JSON.parse(getField("slides")),
    submitted: JSON.parse(getField("submitted")),
    grade_result: JSON.parse(getField("grade_result")),
    approved_topics: APPROVED_TOPICS,
  };
  if (permission === "edit") {
    const apiKey = JSON.parse(getField("haiku_api_key"));
    state.credentials_configured = !!apiKey;
  }
  return JSON.stringify(state);
}
