// Chat plugin - appends messages to a log field
//
// Actions handled:
// - chat.post: Append a message and broadcast it

import { getUsernames, logAppend, logGetRange, sendEvent } from "pxc:sandbox/state";

function resolveNames(ids) {
  return Object.fromEntries(getUsernames([...new Set(ids)]));
}

export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  if (name === "chat.post") {
    const user = context.userId;
    const entry = { user, text: value.text };
    const id = logAppend("messages", JSON.stringify(entry));
    const username = resolveNames([user])[user] || user;
    sendEvent(
      "chat.new",
      JSON.stringify({ id, user, username, text: value.text }),
      null,
      "play",
    );
  }

  return "";
}

export function getState() {
  const messages = JSON.parse(logGetRange("messages", 0, 1000));
  const names = resolveNames(messages.map((m) => m.value.user));
  for (const m of messages) {
    m.value.username = names[m.value.user] || m.value.user;
  }
  return JSON.stringify({ messages });
}
