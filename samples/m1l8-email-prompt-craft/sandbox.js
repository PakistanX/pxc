// email-prompt-craft — practice writing prompts that produce send-ready
// professional emails, graded automatically by an LLM against the M1L8
// "Professional Email Templates" rubric (Technique Application 50%,
// Prompt Quality 25%, Output Quality 25%).
//
// Actions:
// - credentials.save: store the course's Anthropic API key (edit only)
// - scenario.select: pick one of the six fixed scenarios
// - email.generate: send the student's prompt to Claude Haiku, store the
//   result, append it to the attempts log
// - email.submit: (requires >=2 generate calls, i.e. at least one iteration)
//   sends the final prompt+output to Claude Haiku for rubric grading,
//   records the grade via reportScored, locks the activity

import { httpRequest } from "pxc:sandbox/http";
import { reportCompleted, reportScored } from "pxc:sandbox/grading";
import { getField, setField, sendEvent, logAppend } from "pxc:sandbox/state";

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_MODEL = "claude-haiku-4-5-20251001";
const ANTHROPIC_VERSION = "2023-06-01";
const MIN_ATTEMPTS_BEFORE_SUBMIT = 2;

const SCENARIOS = {
  client_followup: "Client follow-up after a meeting (professional, warm, action-oriented)",
  decline_request: "Declining a request diplomatically (firm but respectful)",
  team_intro: "Introducing yourself to a new team (personable, professional)",
  escalate_issue: "Escalating an issue to management (factual, structured, urgent)",
  apology_service: "Apologizing for a service failure (empathetic, accountable, forward-looking)",
  cold_outreach: "Cold outreach to a potential partner (concise, compelling, value-focused)",
};

const GRADING_SYSTEM_PROMPT =
  "Grade student prompt engineering submissions. Score each criterion 1–3. " +
  "Output valid JSON only — no preamble, no markdown fences.";

function gradingRubricPrompt(submission) {
  return (
    "Grade this M1L8 submission: a learner's PROMPT plus the AI-generated EMAIL it produced, " +
    "for one professional email scenario.\n\n" +

    "HOW TO READ THE SUBMISSION\n" +
    "The submission is provided in three labeled parts: SCENARIO, PROMPT, and OUTPUT (the generated email). " +
    "Judge each criterion from the correct part:\n" +
    "- Criteria A and B are judged ONLY from the learner's PROMPT.\n" +
    "- Criterion C is judged from the OUTPUT, verified against the constraints stated in the PROMPT.\n" +
    "Do NOT infer technique use from how polished the email looks. The generator adds structure (subject " +
    "lines, bullets, sign-offs) on its own, so a good-looking email does not prove the PROMPT applied a " +
    "technique. Score techniques ONLY from what is explicitly present in the PROMPT.\n\n" +

    "The PROMPT must use ≥2 of 3 Craft techniques:\n" +
    "- Role Assignment: assigns a specific role/persona with a defined voice, expertise, or style (not " +
    'merely "write an email").\n' +
    "- Context & Constraints: supplies concrete situational detail (named recipient, relationship, " +
    "specific facts) and/or explicit tone or scope limits.\n" +
    "- Format & Success Criteria: states ≥1 explicit, checkable output requirement (subject line, " +
    "word/length limit, required sections or bullet count, specified sign-off).\n\n" +

    "CRITERIA\n\n" +

    "A. Technique Application (50%) — judged from the PROMPT only\n" +
    "3 — ≥2 techniques applied skillfully: role has a specific voice/character; context has ≥3 " +
    "named/specific details; format has ≥1 measurable constraint.\n" +
    "2 — Techniques present but below the level-3 bar: 1 technique applied well with others thin or " +
    "missing, OR 2 techniques present but generic/thin.\n" +
    "1 — No technique meaningfully applied; essentially a bare instruction.\n\n" +

    "B. Prompt Quality (25%) — judged from the PROMPT only\n" +
    "3 — Every element purposeful; no filler; logically ordered role → context → format; specifics " +
    "throughout.\n" +
    "2 — Communicates intent but has notable vagueness or filler; another reader might produce a " +
    "different email from it.\n" +
    "1 — Single sentence or loose, vague instruction that could apply to almost any email.\n\n" +

    "C. Output Quality (25%) — judged from the OUTPUT, verified against the PROMPT's stated constraints\n" +
    "First run two objective checks on the OUTPUT:\n" +
    "  (1) PLACEHOLDER CHECK: Scan for unfilled bracketed placeholders (e.g., [Client Name], [Date], " +
    "[Company], [Title], [Project]). EXCEPTION: ignore a single NAME placeholder on the signature/sign-off " +
    "line (e.g., [Your Name], [Name]) — it is auto-appended by the generator and outside the learner's " +
    "control; do not penalize or flag it. Penalize any OTHER unfilled placeholder in the body.\n" +
    "  (2) CONSTRAINT CHECK: For each explicit, checkable constraint the PROMPT stated (word/length " +
    "limit, required subject line, required sections/bullets, required sign-off), verify whether the " +
    "OUTPUT satisfies it. Material non-compliance (stated word limit clearly exceeded, required subject " +
    "line absent, etc.) caps Output Quality below level 3.\n" +
    "3 — Send-ready; tone calibrated to recipient; no unfilled body placeholders; stated constraints " +
    "satisfied; content specific, not generic.\n" +
    "2 — Core message present but generic sections, tone drift, 1–2 unfilled body placeholders, OR a " +
    "stated constraint not met.\n" +
    "1 — Unusable; unfilled placeholders throughout the body, entirely generic, or off-topic.\n\n" +

    "SCORING\n" +
    "Points: score 3 → 100 pts, 2 → 75 pts, 1 → 50 pts per criterion (before weighting).\n" +
    "Weighted total = (A_pts × 0.50) + (B_pts × 0.25) + (C_pts × 0.25).\n" +
    "Grade: 85–100 = A, 70–84 = B, 55–69 = C, below 55 = F.\n\n" +

    "FLAGS & CONFIDENCE\n" +
    'Record objective findings in flags, e.g., "body_placeholder", "missing_subject_line", ' +
    '"word_limit_exceeded", "prompt_output_indistinct". Set confidence to LOW if PROMPT and OUTPUT ' +
    "cannot be cleanly separated or the submission is malformed; MEDIUM if a criterion sits on the " +
    "border between two levels; otherwise HIGH.\n\n" +

    "Output format: Return only the JSON object with these fields — scores (a, b, c each 1–3), " +
    "feedback (2–3 sentences: one strength, one improvement), confidence (HIGH/MEDIUM/LOW), and " +
    "flags (array of strings, or empty). Do not compute or include a weighted total or letter grade " +
    "— that's derived from your scores separately.\n\n" +
    "Return ONLY this JSON:\n\n" +
    "{\n" +
    '  "scores": {"a": <1-3>, "b": <1-3>, "c": <1-3>},\n' +
    '  "feedback": "<2-3 sentences: one strength, one improvement>",\n' +
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

// The LLM grader is asked for both per-criterion scores AND a weighted
// total/letter grade computed from them — but it's a language model, not a
// calculator, and can (and does) get that arithmetic slightly wrong (e.g.
// reporting 98% for a straight 3/3/3, which no valid combination of the
// rubric's discrete point values can actually produce). Recompute both
// deterministically from the raw scores instead of trusting the model's
// own sum, so the displayed percentage is always mathematically exact.
const SCORE_POINTS = { 1: 50, 2: 75, 3: 100 };
// C or above (>=55%) is the passing threshold — see PASSING_WEIGHTED_TOTAL below.
const PASSING_WEIGHTED_TOTAL = 55;

function recomputeGrade(grade) {
  const a = SCORE_POINTS[grade.scores.a] || 50;
  const b = SCORE_POINTS[grade.scores.b] || 50;
  const c = SCORE_POINTS[grade.scores.c] || 50;
  const weighted = a * 0.5 + b * 0.25 + c * 0.25;
  let letter;
  if (weighted >= 85) letter = "A";
  else if (weighted >= 70) letter = "B";
  else if (weighted >= 55) letter = "C";
  else letter = "F";
  grade.weighted_total = weighted;
  grade.letter_grade = letter;
  grade.passed = weighted >= PASSING_WEIGHTED_TOTAL;
  return grade;
}

// Per-user events must target the calling user ({ userId }), not broadcast
// (null) — null means "every viewer of this activity", which for a
// per-student exercise like this leaks one student's prompt/output/grade
// into every classmate's open tab (they're all polling the same
// activity_id). Only genuinely shared/course-scoped data (e.g.
// credentials.status, since haiku_api_key is a course-scope field visible
// to every course-staff viewer) should broadcast.
function fail(message, userId) {
  sendEvent("generation.error", JSON.stringify(message), { userId: userId }, "play");
  return "";
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
  if (submitted && (name === "scenario.select" || name === "email.generate" || name === "email.submit")) {
    return fail("This activity has already been submitted — submissions are final.", userId);
  }

  if (name === "scenario.select") {
    if (!Object.prototype.hasOwnProperty.call(SCENARIOS, value)) {
      return fail("Unknown scenario.", userId);
    }
    setField("scenario", JSON.stringify(value));
    sendEvent("fields.change.scenario", JSON.stringify(value), { userId: userId }, "play");
    return "";
  }

  if (name === "email.generate") {
    const prompt = (value || "").trim();
    if (!prompt) {
      return fail("Write a prompt first.", userId);
    }
    const scenarioId = JSON.parse(getField("scenario"));
    if (!scenarioId) {
      return fail("Choose a scenario first.", userId);
    }
    const apiKey = JSON.parse(getField("haiku_api_key"));
    if (!apiKey) {
      return fail("This activity's AI key isn't configured yet — ask course staff.", userId);
    }

    const systemPrompt =
      "You are an email-writing assistant embedded in a prompt-engineering exercise. " +
      "Follow the student's instructions exactly and output only the finished email — " +
      "no commentary, no markdown fences, no explanation. The student is targeting this " +
      "scenario: " + SCENARIOS[scenarioId] + ". Do not invent a different scenario, but rely " +
      "on the student's prompt for every specific detail.";

    let output;
    try {
      output = callAnthropic(apiKey, systemPrompt, prompt, 700);
    } catch (e) {
      return fail(e.message, userId);
    }

    setField("prompt_text", JSON.stringify(prompt));
    setField("output_text", JSON.stringify(output));
    const count = JSON.parse(getField("attempt_count")) + 1;
    setField("attempt_count", JSON.stringify(count));
    logAppend("attempts", JSON.stringify({ prompt: prompt, output: output }), null);

    sendEvent(
      "email.generated",
      JSON.stringify({ prompt: prompt, output: output, attempt_count: count }),
      { userId: userId },
      "play"
    );
    return "";
  }

  if (name === "email.submit") {
    const attemptCount = JSON.parse(getField("attempt_count"));
    if (attemptCount < MIN_ATTEMPTS_BEFORE_SUBMIT) {
      return fail(
        "Generate at least " + MIN_ATTEMPTS_BEFORE_SUBMIT + " times (iterate on your prompt) before submitting.",
        userId
      );
    }
    const scenarioId = JSON.parse(getField("scenario"));
    const prompt = JSON.parse(getField("prompt_text"));
    const output = JSON.parse(getField("output_text"));
    if (!scenarioId || !prompt || !output) {
      return fail("Generate an email before submitting.", userId);
    }
    const apiKey = JSON.parse(getField("haiku_api_key"));
    if (!apiKey) {
      return fail("This activity's AI key isn't configured yet — ask course staff.", userId);
    }

    const submission =
      "SCENARIO: " + SCENARIOS[scenarioId] + "\n\nPROMPT:\n" + prompt + "\n\nOUTPUT:\n" + output;

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
      !grade.scores ||
      ![1, 2, 3].includes(grade.scores.a) ||
      ![1, 2, 3].includes(grade.scores.b) ||
      ![1, 2, 3].includes(grade.scores.c)
    ) {
      return fail("Grading response was missing required fields.", userId);
    }
    grade = recomputeGrade(grade);

    setField("grade_result", JSON.stringify(grade));

    // Only a passing grade locks the activity and reaches the LMS gradebook/
    // completion tracker. A failing attempt leaves submitted=false so the
    // student can revise their prompt and resubmit on their own — no grade
    // or completion should ever be recorded for a failing attempt.
    if (grade.passed) {
      setField("submitted", JSON.stringify(true));
      reportScored(Math.max(0, Math.min(1, grade.weighted_total / 100)));
      reportCompleted();
    }

    sendEvent("email.graded", JSON.stringify(grade), { userId: userId }, "play");
    return "";
  }

  return fail("Unknown action.", userId);
}

export function getState(context, permission) {
  const state = {
    scenario: JSON.parse(getField("scenario")),
    prompt_text: JSON.parse(getField("prompt_text")),
    output_text: JSON.parse(getField("output_text")),
    attempt_count: JSON.parse(getField("attempt_count")),
    submitted: JSON.parse(getField("submitted")),
    grade_result: JSON.parse(getField("grade_result")),
    scenarios: SCENARIOS,
  };
  if (permission === "edit") {
    const apiKey = JSON.parse(getField("haiku_api_key"));
    state.credentials_configured = !!apiKey;
  }
  return JSON.stringify(state);
}
