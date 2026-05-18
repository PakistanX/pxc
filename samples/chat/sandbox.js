// Chat plugin - appends messages to a log field
//
// Actions handled:
// - chat.post: Append a message and broadcast it

import { getUsernames, logAppend, logGetBefore, sendEvent } from "pxc:sandbox/state";

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
  // Fetch the latest 1000 messages newest-first, then reverse so the UI
  // renders oldest-at-top and auto-scrolls to the newest at the bottom.
  const messages = JSON.parse(logGetBefore("messages", null, 1000)).reverse();
  const names = resolveNames(messages.map((m) => m.value.user));
  for (const m of messages) {
    m.value.username = names[m.value.user] || m.value.user;
  }
  return JSON.stringify({ messages });
}
