import {
  getField,
  setField,
  sendEvent,
  logAppend,
  logGet,
  logGetRange,
  logDelete,
} from "pxc:sandbox/state";

function getSubmissions() {
  return JSON.parse(logGetRange("submissions", 0, 1000, null));
}

export function getState(context, permission) {
  const instructions = JSON.parse(getField("instructions", null));

  if (permission === "edit") {
    return JSON.stringify({
      instructions,
      criteria: JSON.parse(getField("criteria", null)),
      submissions: getSubmissions(),
    });
  }

  if (permission === "play") {
    const draft = JSON.parse(getField("draft", null));
    const submissionId = JSON.parse(getField("submission_id", null));
    let submission = null;
    if (submissionId >= 0) {
      const entry = JSON.parse(logGet("submissions", submissionId, null));
      if (entry !== null) {
        submission = entry;
      }
    }
    return JSON.stringify({ instructions, draft, submission });
  }

  return JSON.stringify({ instructions });
}

export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  const userId = context.userId || "anonymous";

  if (name === "config.save") {
    if (permission !== "edit") return "";
    setField("instructions", JSON.stringify(value.instructions), null);
    setField("criteria", JSON.stringify(value.criteria), null);
    sendEvent("fields.change.instructions", JSON.stringify(value.instructions), null, "play");
    sendEvent("fields.change.criteria", JSON.stringify(value.criteria), null, "edit");
    return "";
  }

  if (name === "essay.save") {
    if (permission !== "play") return "";
    if (JSON.parse(getField("submission_id", null)) >= 0) return "";
    setField("draft", JSON.stringify(value), null);
    sendEvent("essay.saved", JSON.stringify(true), { userId: userId }, "play");
    return "";
  }

  if (name === "essay.submit") {
    if (permission !== "play") return "";
    if (JSON.parse(getField("submission_id", null)) >= 0) return "";
    const entry = {
      user_id: userId,
      text: value,
      status: "submitted",
      grade: 0,
      grade_comment: "",
    };
    const newId = logAppend("submissions", JSON.stringify(entry), null);
    setField("submission_id", JSON.stringify(newId), null);
    setField("draft", JSON.stringify(value), null);
    sendEvent("essay.submitted", JSON.stringify(true), { userId: userId }, "play");
    sendEvent("submissions.changed", JSON.stringify(getSubmissions()), null, "edit");
    return "";
  }

  if (name === "essay.grade") {
    if (permission !== "edit") return "";
    const targetUserId = value.user_id;
    const grade = value.grade;
    const gradeComment = value.grade_comment;

    const submissionId = JSON.parse(getField("submission_id", { userId: targetUserId }));
    if (submissionId < 0) return "";
    const existing = JSON.parse(logGet("submissions", submissionId, null));
    if (existing === null) return "";

    logDelete("submissions", submissionId, null);
    const updated = {
      user_id: existing.user_id,
      text: existing.text,
      status: "graded",
      grade,
      grade_comment: gradeComment,
    };
    const newId = logAppend("submissions", JSON.stringify(updated), null);
    setField("submission_id", JSON.stringify(newId), { userId: targetUserId });

    sendEvent(
      "essay.graded",
      JSON.stringify({ grade, grade_comment: gradeComment }),
      { userId: targetUserId },
      "play",
    );
    sendEvent("submissions.changed", JSON.stringify(getSubmissions()), null, "edit");
    return "";
  }

  if (name === "essay.delete") {
    if (permission !== "edit") return "";
    const targetUserId = value.user_id;
    const submissionId = JSON.parse(getField("submission_id", { userId: targetUserId }));
    if (submissionId >= 0) {
      logDelete("submissions", submissionId, null);
    }
    setField("submission_id", JSON.stringify(-1), { userId: targetUserId });
    setField("draft", JSON.stringify(""), { userId: targetUserId });
    sendEvent("submissions.changed", JSON.stringify(getSubmissions()), null, "edit");
    return "";
  }

  if (name === "essay.unsubmit") {
    if (permission !== "edit") return "";
    const targetUserId = value.user_id;
    const submissionId = JSON.parse(getField("submission_id", { userId: targetUserId }));
    if (submissionId >= 0) {
      logDelete("submissions", submissionId, null);
    }
    setField("submission_id", JSON.stringify(-1), { userId: targetUserId });
    sendEvent("submissions.changed", JSON.stringify(getSubmissions()), null, "edit");
    return "";
  }

  return "";
}
