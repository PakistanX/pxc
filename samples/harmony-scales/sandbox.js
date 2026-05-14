import { getField, setField, sendEvent } from "pxc:sandbox/state";

export function onAction(name, data, context, permission) {
  if (name === "config.save") {
    if (permission !== "edit") return "";
    const value = JSON.parse(data);
    setField("scale", JSON.stringify(value.scale), null);
    sendEvent("fields.change.scale", JSON.stringify(value.scale), null, "play");
  }
  return "";
}

export function getState(context, permission) {
  return JSON.stringify({
    scale: JSON.parse(getField("scale", null)),
  });
}
