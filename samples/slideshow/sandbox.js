// Slideshow plugin - reveal.js presentation with media uploads.
//
// Actions handled:
// - config.save:  Save the slides_html
// - file.upload:  Store a static file in the "media" storage namespace
// - file.delete:  Remove a file from the "media" storage namespace

import { getField, sendEvent, setField } from "pxc:sandbox/state";
import { storageDelete, storageExists, storageList, storageUrl, storageWrite } from "pxc:sandbox/storage";

function base64ToBytes(base64) {
  const binString = atob(base64);
  const bytes = new Uint8Array(binString.length);
  for (let i = 0; i < binString.length; i++) {
    bytes[i] = binString.charCodeAt(i);
  }
  return bytes;
}

function sanitizeFilename(name) {
  // Keep the basename only, drop any path separators and traversal sequences.
  const basename = String(name).split(/[\\/]/).pop() || "";
  const cleaned = basename
    .replace(/\.\.+/g, ".")
    .replace(/[^A-Za-z0-9._-]/g, "_")
    .replace(/^\.+/, "");
  return cleaned;
}

function currentFiles() {
  // storage-list returns [directories, files]; uploads here are flat so we
  // ignore the directories list.
  if(!storageExists("media", "", null)) {
    return [];
  }
  const [, files] = storageList("media", "", null);
  return files.map((filename) => ({
    filename,
    url: storageUrl("media", filename, null),
  }));
}

export function onAction(name, data, context, permission) {
  const value = JSON.parse(data);
  if (name === "config.save") {
    if (permission !== "edit") {
      console.log("config.save rejected: permission is " + permission);
      return "";
    }
    setField("slides_html", JSON.stringify(value.slides_html));
    sendEvent("fields.change.slides_html", JSON.stringify(value.slides_html), null, "play");
  } else if (name === "file.upload") {
    if (permission !== "edit") {
      console.log("file.upload rejected: permission is " + permission);
      return "";
    }
    const match = String(value.data || "").match(/^data:([^;]+);base64,(.+)$/);
    if (!match) {
      console.log("file.upload rejected: invalid data URI");
      return "";
    }
    const filename = sanitizeFilename(value.filename);
    if (!filename) {
      console.log("file.upload rejected: empty filename");
      return "";
    }
    storageWrite("media", filename, base64ToBytes(match[2]), null);
    sendEvent("files.changed", JSON.stringify(currentFiles()), null, "play");
  } else if (name === "file.delete") {
    if (permission !== "edit") {
      console.log("file.delete rejected: permission is " + permission);
      return "";
    }
    const filename = sanitizeFilename(value.filename);
    if (!filename) return "";
    storageDelete("media", filename, null);
    sendEvent("files.changed", JSON.stringify(currentFiles()), null, "play");
  }
  return "";
}

export function getState() {
  return JSON.stringify({
    slides_html: JSON.parse(getField("slides_html")),
    files: currentFiles(),
  });
}
