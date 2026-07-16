// m2l6-visual-story — practice writing 3 image-generation prompts (each
// with subject/style/composition/mood/context) plus 3 captions forming one
// visual narrative, graded automatically by an LLM against the M2L6 binary
// checklist rubric (6 criteria, ~16.7% weight each).
//
// Design note: grading is text-only — students do not submit images, only
// prompts and captions (per the grading toolkit: "grading focuses on your
// prompts and captions, not the images themselves... grading images
// requires expensive vision models"). No in-app image generation either.
//
// Actions:
// - credentials.save: store the course's Anthropic API key (edit only)
// - story.save: validate + persist the draft (topic, 3 prompt/caption pairs)
// - story.submit: re-validate the persisted draft, send it to Claude Haiku
//   for rubric grading, record the grade via reportScored, lock

import { httpRequest } from "pxc:sandbox/http";
import { reportCompleted, reportScored } from "pxc:sandbox/grading";
import { getField, setField, sendEvent } from "pxc:sandbox/state";

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_MODEL = "claude-haiku-4-5-20251001";
const ANTHROPIC_VERSION = "2023-06-01";
const REQUIRED_IMAGE_COUNT = 3;

const APPROVED_TOPICS = [
  "A day in the life of a future city",
  "The journey of a product from concept to customer",
  "A visual metaphor of a patient's visit to a healthcare clinic",
];

const GRADING_SYSTEM_PROMPT =
  "Grade student prompt engineering submissions against a binary checklist. Each criterion is " +
  "Y (pass) or N (fail). Output valid JSON only — no preamble, no markdown fences.";

function gradingRubricPrompt(submission) {
  return (
    "Grade this M2L6 submission: 3 image-generation prompts and 3 captions forming one visual " +
    "narrative. Students do not submit images — evaluate prompts and captions only.\n\n" +

    "CRITERIA (each is Y or N)\n\n" +

    "C1. Image Count\n" +
    "Y — Exactly 3 prompts and exactly 3 captions are present.\n" +
    "N — Fewer or more than 3 of either.\n\n" +

    "C2. Prompt Elements\n" +
    "Y — Every prompt contains all 5 required elements: (1) Subject — what is depicted; (2) Style — " +
    "artistic approach (e.g., photorealistic, watercolor, minimalist); (3) Composition — framing or " +
    "camera angle (e.g., close-up, wide shot, aerial view); (4) Mood/Lighting — emotional tone or " +
    "light quality; (5) Context/Setting — environment, time of day, or background. All 5 must be " +
    "present in all 3 prompts.\n" +
    "N — Any prompt is missing one or more of the 5 elements.\n\n" +

    "C3. Style Anchor Consistency\n" +
    "Y — A consistent style phrase or description appears across all 3 prompts (identical or " +
    "near-identical wording anchoring the visual style, e.g., \"minimalist digital illustration, " +
    'muted earth tones" repeated in each prompt).\n' +
    "N — Style descriptions vary significantly between prompts, or no shared style phrase is " +
    "present.\n\n" +

    "C4. Caption Narrative\n" +
    "Y — The 3 captions read as a sequential story with a clear beginning, middle, and end. Each " +
    "caption advances the narrative rather than simply describing the image in isolation.\n" +
    "N — Captions are independent image descriptions with no narrative progression, or fewer than 3 " +
    "captions are present.\n\n" +

    "C5. Topic Match\n" +
    "Y — The narrative clearly matches one of the three approved topics: (1) A day in the life of a " +
    "future city, (2) The journey of a product from concept to customer, (3) A visual metaphor of a " +
    "patient's visit to a healthcare clinic.\n" +
    "N — The narrative does not match any of the three approved topics, or the topic is ambiguous.\n\n" +

    "C6. File Size / Submission Format\n" +
    "Y — Submission contains only prompts and captions (no embedded images submitted for grading); " +
    "text is present and readable.\n" +
    "N — Submission is missing prompts or captions, or is otherwise unreadable.\n" +
    "Note: C6 defaults to Y if the submission text is present and parseable. Flag if anything appears " +
    "missing.\n\n" +

    "SCORING\n" +
    "Each Y = 1 point. Total score = number of Y verdicts out of 6.\n" +
    "Weighted total (out of 100) = (Y_count / 6) × 100, rounded to one decimal.\n" +
    "Grade: 6/6=100 A, 5/6=83.3 B, 4/6=66.7 C, ≤3/6=F. Do not compute or include " +
    "y_count/weighted_total/letter_grade yourself — those are derived from your criteria verdicts " +
    "separately.\n\n" +

    "Return ONLY this JSON:\n\n" +
    "{\n" +
    '  "criteria": {\n' +
    '    "c1_image_count": "<Y/N>",\n' +
    '    "c2_prompt_elements": "<Y/N>",\n' +
    '    "c3_style_anchor": "<Y/N>",\n' +
    '    "c4_caption_narrative": "<Y/N>",\n' +
    '    "c5_topic_match": "<Y/N>",\n' +
    '    "c6_submission_format": "<Y/N>"\n' +
    "  },\n" +
    '  "feedback": "<2-3 sentences: which criteria passed/failed and the single most impactful fix>",\n' +
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
    // temperature 0: grading must be deterministic — the same submission
    // scoring differently between runs means the rubric is judging sampling
    // noise instead of the actual submission.
    temperature: 0,
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
// trusting the model's own sum, matching the rubric's score table exactly
// (6/6=100 A, 5/6=83.3 B, 4/6=66.7 C, <=3/6=F).
const CRITERIA_KEYS = [
  "c1_image_count",
  "c2_prompt_elements",
  "c3_style_anchor",
  "c4_caption_narrative",
  "c5_topic_match",
  "c6_submission_format",
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

// Structural-only validation — element/style/narrative/topic quality is the
// LLM grader's job (C2-C5); this just prevents an obviously incomplete
// draft from wasting an API call.
function validateDraft(topic, images) {
  if (!APPROVED_TOPICS.includes(topic)) {
    return "Choose one of the three approved topics.";
  }
  if (!Array.isArray(images) || images.length !== REQUIRED_IMAGE_COUNT) {
    return "You need exactly " + REQUIRED_IMAGE_COUNT + " image prompts with captions.";
  }
  for (let i = 0; i < images.length; i++) {
    if (!images[i].prompt || !images[i].prompt.trim()) {
      return "Image " + (i + 1) + " needs a prompt.";
    }
    if (!images[i].caption || !images[i].caption.trim()) {
      return "Image " + (i + 1) + " needs a caption.";
    }
  }
  return null;
}

function buildSubmissionText(topic, images) {
  const parts = ["TOPIC: " + topic];
  images.forEach((img, i) => {
    parts.push("PROMPT " + (i + 1) + ": " + img.prompt);
    parts.push("CAPTION " + (i + 1) + ": " + img.caption);
  });
  return parts.join("\n\n");
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
  if (submitted && (name === "story.save" || name === "story.submit")) {
    return fail("This activity has already been submitted — submissions are final.", userId);
  }

  if (name === "story.save") {
    const topic = value.topic || "";
    const images = value.images || [];

    const error = validateDraft(topic, images);
    if (error) {
      return fail(error, userId);
    }

    setField("topic", JSON.stringify(topic));
    setField("images", JSON.stringify(images));

    sendEvent(
      "story.saved",
      JSON.stringify({ topic: topic, images: images }),
      { userId: userId },
      "play"
    );
    return "";
  }

  if (name === "story.submit") {
    const topic = JSON.parse(getField("topic"));
    const images = JSON.parse(getField("images"));

    const error = validateDraft(topic, images);
    if (error) {
      return fail("Save a complete draft first: " + error, userId);
    }
    const apiKey = JSON.parse(getField("haiku_api_key"));
    if (!apiKey) {
      return fail("This activity's AI key isn't configured yet — ask course staff.", userId);
    }

    const submission = buildSubmissionText(topic, images);

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

    sendEvent("story.graded", JSON.stringify(grade), { userId: userId }, "play");
    return "";
  }

  return fail("Unknown action.", userId);
}

export function getState(context, permission) {
  const state = {
    topic: JSON.parse(getField("topic")),
    images: JSON.parse(getField("images")),
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
