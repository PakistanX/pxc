// m3l2-data-analysis-toolkit — practice a 5-stage data-analysis prompt
// workflow (upload & understand, explore, generate insights, visualize,
// summarize & recommend) against one of four provided datasets, graded
// automatically by an LLM against the M3L2 binary checklist rubric (4
// criteria, 25% weight each).
//
// Design note: students actually run the Stage 2/3/4 prompts with whatever
// AI tool they use against the downloadable dataset (this activity doesn't
// call an LLM to analyze data in-tool — the point being graded is the
// *prompts* and the resulting write-up, not generating an analysis in-tool).
// They transcribe the dataset choice, AI-generated description, 2
// visualization title/captions, executive summary, and the 3 stage prompts
// into this form — exactly the structured text a real submission's
// markitdown-extracted .docx/.pdf would produce — then submit that for
// rubric grading. No in-app "analyze data" step, unlike the meeting
// activity; images/charts themselves are never submitted or graded, only
// their labels and captions (matching the grading toolkit's pre-processing
// note).
//
// Actions:
// - credentials.save: store the course's Anthropic API key (edit only)
// - draft.save: validate + persist the draft
// - toolkit.submit: re-validate the persisted draft, send it to Claude
//   Haiku for rubric grading, record the grade via reportScored, lock only
//   on a passing grade

import { httpRequest } from "pxc:sandbox/http";
import { reportCompleted, reportScored } from "pxc:sandbox/grading";
import { getField, setField, sendEvent } from "pxc:sandbox/state";

const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";
const ANTHROPIC_MODEL = "claude-haiku-4-5-20251001";
const ANTHROPIC_VERSION = "2023-06-01";
const REQUIRED_VISUALIZATION_COUNT = 2;

const APPROVED_DATASETS = {
  "Sales / Revenue Data": "Public_M3L2_Datasets.xlsx (Sheet: Sales_Revenue)",
  "Survey Responses": "Public_M3L2_Datasets.xlsx (Sheet: Survey_Responses)",
  "Website Analytics": "Public_M3L2_Datasets.xlsx (Sheet: Website_Analytics)",
  "Urban Development": "Public_M3L2_Datasets.xlsx (Sheet: Urban_Development)",
};

const GRADING_SYSTEM_PROMPT =
  "Grade student prompt engineering submissions against a binary checklist. Each criterion is " +
  "Y (pass) or N (fail). Output valid JSON only — no preamble, no markdown fences.";

function gradingRubricPrompt(submission) {
  return (
    "Grade this M3L2 submission: a data analysis project document containing a dataset " +
    "description, two labeled visualizations with captions, an executive summary, and three " +
    "documented prompts (Stages 2, 3, and 4). Apply each criterion strictly and independently.\n\n" +

    "CRITERIA (each is Y or N)\n\n" +

    "C1. Dataset Description\n" +
    "Y — Submission includes the dataset name and a source link or filename, AND includes a " +
    "description that mentions at least 2 of the following: row count, column names, data types, " +
    "data quality issues.\n" +
    "N — Dataset is not identified, or AI description is absent or too vague to contain any of the " +
    "required metadata.\n\n" +

    "C2. Visualization Count\n" +
    'Y — Exactly 2 visualizations are present in the submission, each labeled as "Viz 1" or "Viz 2" ' +
    "(or equivalent sequential labeling), each with a descriptive title AND an interpretive caption " +
    'that states a key insight (not just what the chart shows). A caption like "Revenue by region" ' +
    "does not qualify — it must state what the pattern means (e.g., \"Region B underperformed in " +
    'Q3 due to reduced inventory").\n' +
    "N — Fewer or more than 2 labeled visualizations, or any visualization is missing a title or " +
    "interpretive caption.\n\n" +

    "C3. Executive Summary\n" +
    'Y — A section labeled "Executive Summary" (or equivalent) is present, contains 100–150 words ' +
    "(estimate based on density), leads with the most important finding as the first sentence, and " +
    "includes at least 1 specific actionable recommendation. Generic recommendations (e.g., " +
    '"improve performance") do not qualify — they must name a specific action (e.g., "increase ' +
    'marketing budget in Region B by 15%").\n' +
    "N — Section is absent, too short (clearly under 100 words), does not lead with a finding, or " +
    "lacks 1 specific actionable recommendation.\n\n" +

    "C4. Prompt Documentation\n" +
    'Y — Exactly 3 prompts are present, labeled "Stage 2", "Stage 3", and "Stage 4" (or equivalent ' +
    "labels clearly corresponding to these stages). At least 2 distinct CAR techniques are visibly " +
    "present across the 3 prompts. Count any of: (1) Role Assignment — a named persona (e.g., " +
    '"You are a senior data analyst..."); (2) Context & Constraints — specific dataset or domain ' +
    "details in the prompt; (3) Format & Success Criteria — an explicit output format, word count, " +
    "or structure requirement; (4) Task Decomposition — structured multi-part request within a " +
    "single prompt; (5) Chain-of-Thought — instruction to show calculations, reasoning steps, or " +
    "logic step by step.\n" +
    "N — Fewer than 3 prompts, or prompts are not labeled by stage, or fewer than 2 distinct CAR " +
    "techniques are identifiable.\n\n" +

    "SCORING\n" +
    "Each Y = 1 point. Total score = number of Y verdicts out of 4.\n" +
    "Weighted total (out of 100) = (Y_count / 4) × 100.\n" +
    "Grade: 4/4=100 A, 3/4=75 B, 2/4=50 C, ≤1/4=F. Do not compute or include y_count/weighted_total/" +
    "letter_grade yourself — those are derived from your criteria verdicts separately.\n\n" +

    "Return ONLY this JSON:\n\n" +
    "{\n" +
    '  "criteria": {\n' +
    '    "c1_dataset_description": "<Y/N>",\n' +
    '    "c2_visualization_count": "<Y/N>",\n' +
    '    "c3_executive_summary": "<Y/N>",\n' +
    '    "c4_prompt_documentation": "<Y/N>"\n' +
    "  },\n" +
    '  "feedback": "<2-3 sentences: note which criteria passed/failed and the single most ' +
    'impactful fix>",\n' +
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

const CRITERIA_KEYS = [
  "c1_dataset_description",
  "c2_visualization_count",
  "c3_executive_summary",
  "c4_prompt_documentation",
];

// 50% (2 of 4 criteria) is the passing threshold, per the grading toolkit.
const PASSING_Y_COUNT = 2;

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
  grade.passed = yCount >= PASSING_Y_COUNT;
  return grade;
}

// Structural-only validation — deliberately does NOT check description
// depth, caption insightfulness, summary quality, or CAR-technique count.
// Those are the LLM grader's job (C1/C2/C3/C4); this just prevents an
// obviously incomplete draft from wasting an API call.
function validateDraft(dataset, aiDescription, visualizations, executiveSummary, stage2, stage3, stage4) {
  if (!Object.prototype.hasOwnProperty.call(APPROVED_DATASETS, dataset)) {
    return "Choose one of the four approved datasets.";
  }
  if (!aiDescription || !aiDescription.trim()) {
    return "Add the AI-generated dataset description.";
  }
  if (!Array.isArray(visualizations) || visualizations.length !== REQUIRED_VISUALIZATION_COUNT) {
    return "You must have exactly " + REQUIRED_VISUALIZATION_COUNT + " visualizations.";
  }
  for (let i = 0; i < visualizations.length; i++) {
    const viz = visualizations[i];
    if (!viz.title || !viz.title.trim() || !viz.caption || !viz.caption.trim()) {
      return "Visualization " + (i + 1) + " needs both a title and a caption.";
    }
  }
  if (!executiveSummary || !executiveSummary.trim()) {
    return "Add the executive summary.";
  }
  if (!stage2 || !stage2.trim() || !stage3 || !stage3.trim() || !stage4 || !stage4.trim()) {
    return "All three stage prompts (Stage 2, Stage 3, Stage 4) are required.";
  }
  return null;
}

function buildSubmissionText(dataset, aiDescription, visualizations, executiveSummary, stage2, stage3, stage4) {
  const vizText = visualizations
    .map((v, i) => "VISUALIZATION " + (i + 1) + " — " + v.title + ": " + v.caption)
    .join("\n");
  return (
    "DATASET: " + dataset + " | Source: " + APPROVED_DATASETS[dataset] + "\n" +
    "AI DESCRIPTION: " + aiDescription + "\n" +
    vizText + "\n" +
    "EXECUTIVE SUMMARY:\n" + executiveSummary + "\n" +
    "STAGE 2 PROMPT: " + stage2 + "\n" +
    "STAGE 3 PROMPT: " + stage3 + "\n" +
    "STAGE 4 PROMPT: " + stage4
  );
}

// Per-user events must target the calling user ({ userId }), not broadcast
// (null) — null means "every viewer of this activity", which for a
// per-student exercise like this leaks one student's submission into every
// classmate's open tab.
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
  if (submitted && (name === "draft.save" || name === "toolkit.submit")) {
    return fail("This activity has already been submitted — submissions are final.", userId);
  }

  if (name === "draft.save") {
    const dataset = value.dataset || "";
    const aiDescription = value.ai_description || "";
    const visualizations = (value.visualizations || []).slice(0, REQUIRED_VISUALIZATION_COUNT);
    const executiveSummary = value.executive_summary || "";
    const stage2 = value.stage2_prompt || "";
    const stage3 = value.stage3_prompt || "";
    const stage4 = value.stage4_prompt || "";

    const error = validateDraft(dataset, aiDescription, visualizations, executiveSummary, stage2, stage3, stage4);
    if (error) {
      return fail(error, userId);
    }

    setField("dataset", JSON.stringify(dataset));
    setField("ai_description", JSON.stringify(aiDescription));
    setField("visualizations", JSON.stringify(visualizations));
    setField("executive_summary", JSON.stringify(executiveSummary));
    setField("stage2_prompt", JSON.stringify(stage2));
    setField("stage3_prompt", JSON.stringify(stage3));
    setField("stage4_prompt", JSON.stringify(stage4));

    sendEvent(
      "draft.saved",
      JSON.stringify({
        dataset: dataset,
        ai_description: aiDescription,
        visualizations: visualizations,
        executive_summary: executiveSummary,
        stage2_prompt: stage2,
        stage3_prompt: stage3,
        stage4_prompt: stage4,
      }),
      { userId: userId },
      "play"
    );
    return "";
  }

  if (name === "toolkit.submit") {
    const dataset = JSON.parse(getField("dataset"));
    const aiDescription = JSON.parse(getField("ai_description"));
    const visualizations = JSON.parse(getField("visualizations"));
    const executiveSummary = JSON.parse(getField("executive_summary"));
    const stage2 = JSON.parse(getField("stage2_prompt"));
    const stage3 = JSON.parse(getField("stage3_prompt"));
    const stage4 = JSON.parse(getField("stage4_prompt"));

    const error = validateDraft(dataset, aiDescription, visualizations, executiveSummary, stage2, stage3, stage4);
    if (error) {
      return fail("Save a complete draft first: " + error, userId);
    }
    const apiKey = JSON.parse(getField("haiku_api_key"));
    if (!apiKey) {
      return fail("This activity's AI key isn't configured yet — ask course staff.", userId);
    }

    const submission = buildSubmissionText(
      dataset, aiDescription, visualizations, executiveSummary, stage2, stage3, stage4
    );

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

    // Only a passing grade locks the activity and reaches the LMS gradebook/
    // completion tracker. A failing attempt leaves submitted=false so the
    // student can revise their write-up and resubmit on their own — no
    // grade or completion should ever be recorded for a failing attempt.
    if (grade.passed) {
      setField("submitted", JSON.stringify(true));
      reportScored(Math.max(0, Math.min(1, grade.weighted_total / 100)));
      reportCompleted();
    }

    sendEvent("toolkit.graded", JSON.stringify(grade), { userId: userId }, "play");
    return "";
  }

  return fail("Unknown action.", userId);
}

export function getState(context, permission) {
  const state = {
    dataset: JSON.parse(getField("dataset")),
    ai_description: JSON.parse(getField("ai_description")),
    visualizations: JSON.parse(getField("visualizations")),
    executive_summary: JSON.parse(getField("executive_summary")),
    stage2_prompt: JSON.parse(getField("stage2_prompt")),
    stage3_prompt: JSON.parse(getField("stage3_prompt")),
    stage4_prompt: JSON.parse(getField("stage4_prompt")),
    submitted: JSON.parse(getField("submitted")),
    grade_result: JSON.parse(getField("grade_result")),
    approved_datasets: Object.keys(APPROVED_DATASETS),
  };
  if (permission === "edit") {
    const apiKey = JSON.parse(getField("haiku_api_key"));
    state.credentials_configured = !!apiKey;
  }
  return JSON.stringify(state);
}
