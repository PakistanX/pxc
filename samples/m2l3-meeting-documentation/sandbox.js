// m2l3-meeting-documentation — practice building a reusable prompt template
// that converts a meeting transcript into a 5-section structured summary,
// graded automatically by an LLM against the M2L3 binary checklist rubric
// (Meeting Transcript/Notes, Prompt Template Design, Five-Section Output,
// Action Item Completeness — each Y/N, 25% weight).
//
// Actions:
// - credentials.save: store the course's Anthropic API key (edit only)
// - meeting.generate: apply the student's prompt template to their
//   transcript via Claude Haiku, store the result, append to attempts log
// - meeting.save_refinement: persist the refinement note (what/why changed)
// - meeting.submit: (requires >=2 generate calls, i.e. a refined attempt,
//   plus a non-empty refinement note) sends the full submission to Claude
//   Haiku for rubric grading, records the grade via reportScored, locks

import { httpRequest } from "pxc:sandbox/http";
import { reportCompleted, reportScored } from "pxc:sandbox/grading";
import { getField, setField, sendEvent, logAppend } from "pxc:sandbox/state";

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_MODEL = "claude-haiku-4-5-20251001";
const ANTHROPIC_VERSION = "2023-06-01";
const MIN_ATTEMPTS_BEFORE_SUBMIT = 2;

// Faithfully executes the learner's own prompt template instead of imposing
// house formatting — grading (C2 etc.) evaluates the learner's prompt, and
// that only means something if the output isn't auto-structured/auto-
// corrected regardless of what the learner actually wrote.
const GENERATION_SYSTEM_PROMPT =
  "You are an AI writing assistant inside a prompt-engineering exercise. A learner has written a " +
  "prompt template, and your job is to execute THAT template faithfully to produce a meeting " +
  "summary. The learner is being graded on how well their template is written, so your output must " +
  "reflect their instructions exactly. Do not add sections, headings, tables, or formatting the " +
  "learner did not ask for, and do not silently correct or improve a weak template.\n\n" +
  "Rules:\n" +
  "1. Follow the learner's prompt template exactly as written. If it specifies sections, labels, " +
  "tables, or formats, reproduce them precisely. If it omits something, leave it omitted — do not " +
  "supply it yourself.\n" +
  "2. Use ONLY information present in the transcript. Do not invent participants, decisions, owners, " +
  "deadlines, priorities, or any other detail. If the template asks for a field the transcript does " +
  'not contain, follow the learner\'s instruction for handling missing values; if they gave none, ' +
  'write "Not specified".\n' +
  "3. Be consistent. Given the same template and transcript, produce the same summary. Do not vary " +
  "structure or wording between runs.\n" +
  "4. Output only the summary — no preamble, commentary, or explanation.";

function generationUserMessage(prompt, transcript) {
  return "Learner's prompt template:\n" + prompt + "\n\nMeeting transcript:\n" + transcript;
}

const GRADING_SYSTEM_PROMPT =
  "Grade student prompt engineering submissions against a binary checklist. Each criterion is " +
  "Y (pass) or N (fail). Output valid JSON only — no preamble, no markdown fences.";

function gradingRubricPrompt(submission) {
  return (
    "Grade this M2L3 submission: a meeting documentation project containing a meeting transcript " +
    "or detailed notes, a prompt template, and an AI-generated structured summary with five labeled " +
    "sections. Apply each criterion strictly and independently.\n\n" +

    "C1. Meeting Transcript or Notes\n" +
    "Y — Submission includes a meeting transcript or detailed meeting notes that are realistic and " +
    "sufficiently detailed for a prompt to act on. Content must include at least 3 of the following: " +
    "named participants, a stated meeting purpose or topic, specific decisions or discussion points, " +
    "and identifiable action items or tasks.\n" +
    "N — No transcript or notes are provided, or the content is a placeholder, is too vague to act " +
    'on (e.g., "a meeting happened"), or contains fewer than 3 of the required elements.\n\n' +

    "C2. Prompt Template Design\n" +
    "Before scoring this criterion, evaluate each of the four required techniques individually. " +
    'For each one, quote the exact phrase from the prompt template that satisfies it, or write "none ' +
    'found." Base the Y/N verdict only on whether a satisfying phrase exists — a technique counts as ' +
    "present even if it is briefly or plainly worded.\n\n" +
    "The four required techniques:\n" +
    '(1) Role Assignment — a named persona for the AI (e.g., "You are an executive assistant").\n' +
    "(2) Context & Constraints — at least ONE explicit constraint on output scope, tone, or length. " +
    "Any one of the following counts as satisfying this: a tone instruction (e.g., \"professional " +
    "tone,\" \"neutral tone\"), a length limit (e.g., \"under 300 words,\" \"keep it brief\"), or a " +
    "scope rule (e.g., \"use only the transcript,\" \"don't add anything not stated,\" \"focus on " +
    "decisions\"). Do NOT require the constraint to be strongly or elaborately worded — a single " +
    "plainly-stated scope, tone, or length constraint is sufficient.\n" +
    "(3) Format & Success Criteria — explicit output structure requiring all 5 sections.\n" +
    "(4) Task Decomposition (T6) — the prompt breaks the output into distinct numbered or labeled " +
    "sections.\n\n" +
    "Y — All four techniques are present (a satisfying phrase was found for each).\n" +
    "N — Any one of the four techniques is absent (no satisfying phrase found for it).\n\n" +

    "C3. Five-Section Summary Output\n" +
    "Y — The AI-generated output contains all five labeled sections: (1) Meeting Overview, " +
    "(2) Key Decisions, (3) Action Items, (4) Open Questions, and (5) Next Meeting Agenda. Each " +
    "section must be non-empty. The Meeting Overview must be 2–3 sentences. Key Decisions must be a " +
    "numbered list with at least one decision owner named. Action Items must appear as a table with " +
    "columns for Task, Owner, Deadline, and Priority.\n" +
    "N — Any section is missing or empty, Meeting Overview is not 2–3 sentences, Key Decisions are " +
    "not numbered or lack a named owner, or Action Items are not in table format.\n\n" +

    "C4. Action Item Completeness\n" +
    "Y — Every action item in the Action Items table has all three of the following fields " +
    "populated: Owner, Deadline, and Priority. The submission must also include evidence of prompt " +
    "refinement: either a revised prompt or a written note describing what was changed and why.\n" +
    "N — Any action item is missing an Owner, Deadline, or Priority field; or no evidence of prompt " +
    "refinement is present.\n\n" +

    "SCORING\n" +
    "Each Y = 1 point. Total score = number of Y verdicts out of 4.\n" +
    "Weighted total (out of 100) = (Y_count / 4) × 100.\n" +
    "Grade: 4/4 = 100 → A, 3/4 = 75 → B, 2/4 = 50 → C, ≤1/4 → F. Do not compute or include " +
    "y_count/weighted_total/letter_grade yourself — those are derived from your criteria verdicts " +
    "separately.\n\n" +

    "Return ONLY this JSON:\n\n" +
    "{\n" +
    '  "criteria": {\n' +
    '    "c1_transcript_or_notes": "<Y/N>",\n' +
    '    "c2_prompt_template_design": "<Y/N>",\n' +
    '    "c3_five_section_output": "<Y/N>",\n' +
    '    "c4_action_item_completeness": "<Y/N>"\n' +
    "  },\n" +
    '  "feedback": "<2-3 sentences>",\n' +
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
    // temperature 0: both generation and grading need to be deterministic —
    // the same learner prompt/transcript (or the same submission at grading
    // time) must produce the same output/verdicts every run, otherwise the
    // rubric is scoring sampling noise instead of the actual submission.
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
// trusting the model's own sum, so the displayed percentage is always
// mathematically exact (always an exact multiple of 25 here).
const CRITERIA_KEYS = [
  "c1_transcript_or_notes",
  "c2_prompt_template_design",
  "c3_five_section_output",
  "c4_action_item_completeness",
];

function recomputeGrade(grade) {
  const yCount = CRITERIA_KEYS.filter((k) => grade.criteria[k] === "Y").length;
  let letter;
  if (yCount === 4) letter = "A";
  else if (yCount === 3) letter = "B";
  else if (yCount === 2) letter = "C";
  else letter = "F";
  grade.y_count = yCount;
  grade.weighted_total = (yCount / 4) * 100;
  grade.letter_grade = letter;
  return grade;
}

// Per-user events must target the calling user ({ userId }), not broadcast
// (null) — null means "every viewer of this activity", which for a
// per-student exercise like this leaks one student's transcript/prompt/
// output/grade into every classmate's open tab.
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
  if (
    submitted &&
    (name === "meeting.generate" || name === "meeting.save_refinement" || name === "meeting.submit")
  ) {
    return fail("This activity has already been submitted — submissions are final.", userId);
  }

  if (name === "meeting.generate") {
    const transcript = (value.transcript || "").trim();
    const prompt = (value.prompt || "").trim();
    if (!transcript) {
      return fail("Paste your meeting transcript or notes first.", userId);
    }
    if (!prompt) {
      return fail("Write your prompt template first.", userId);
    }
    const apiKey = JSON.parse(getField("haiku_api_key"));
    if (!apiKey) {
      return fail("This activity's AI key isn't configured yet — ask course staff.", userId);
    }

    let output;
    try {
      output = callAnthropic(apiKey, GENERATION_SYSTEM_PROMPT, generationUserMessage(prompt, transcript), 900);
    } catch (e) {
      return fail(e.message, userId);
    }

    setField("transcript_text", JSON.stringify(transcript));
    setField("prompt_text", JSON.stringify(prompt));
    setField("output_text", JSON.stringify(output));
    const count = JSON.parse(getField("attempt_count")) + 1;
    setField("attempt_count", JSON.stringify(count));
    logAppend("attempts", JSON.stringify({ prompt: prompt, output: output }), null);

    sendEvent(
      "meeting.generated",
      JSON.stringify({ transcript: transcript, prompt: prompt, output: output, attempt_count: count }),
      { userId: userId },
      "play"
    );
    return "";
  }

  if (name === "meeting.save_refinement") {
    const note = (value || "").trim();
    setField("refinement_note", JSON.stringify(note));
    sendEvent("refinement.saved", JSON.stringify({ refinement_note: note }), { userId: userId }, "play");
    return "";
  }

  if (name === "meeting.submit") {
    const attemptCount = JSON.parse(getField("attempt_count"));
    if (attemptCount < MIN_ATTEMPTS_BEFORE_SUBMIT) {
      return fail(
        "Generate at least " + MIN_ATTEMPTS_BEFORE_SUBMIT + " times (refine your prompt and " +
          "regenerate) before submitting.",
        userId
      );
    }
    const refinementNote = JSON.parse(getField("refinement_note"));
    if (!refinementNote) {
      return fail("Write a refinement note describing what you changed and why before submitting.", userId);
    }
    const transcript = JSON.parse(getField("transcript_text"));
    const prompt = JSON.parse(getField("prompt_text"));
    const output = JSON.parse(getField("output_text"));
    if (!transcript || !prompt || !output) {
      return fail("Generate a summary before submitting.", userId);
    }
    const apiKey = JSON.parse(getField("haiku_api_key"));
    if (!apiKey) {
      return fail("This activity's AI key isn't configured yet — ask course staff.", userId);
    }

    const submission =
      "TRANSCRIPT:\n" + transcript +
      "\n\nPROMPT TEMPLATE:\n" + prompt +
      "\n\nAI OUTPUT:\n" + output +
      "\n\nREFINEMENT NOTE (if present):\n" + refinementNote;

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

    sendEvent("meeting.graded", JSON.stringify(grade), { userId: userId }, "play");
    return "";
  }

  return fail("Unknown action.", userId);
}

export function getState(context, permission) {
  const state = {
    transcript_text: JSON.parse(getField("transcript_text")),
    prompt_text: JSON.parse(getField("prompt_text")),
    output_text: JSON.parse(getField("output_text")),
    refinement_note: JSON.parse(getField("refinement_note")),
    attempt_count: JSON.parse(getField("attempt_count")),
    submitted: JSON.parse(getField("submitted")),
    grade_result: JSON.parse(getField("grade_result")),
  };
  if (permission === "edit") {
    const apiKey = JSON.parse(getField("haiku_api_key"));
    state.credentials_configured = !!apiKey;
  }
  return JSON.stringify(state);
}
