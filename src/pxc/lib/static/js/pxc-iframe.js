// Runs inside a sandboxed iframe (null origin). Waits for pxc:init from the
// host page, then loads the activity's ui.js and calls setup(activity).
// All server communication is proxied through the host via postMessage.

const _pendingEvents = [];
let _activity = null;

let _initResolve;
const _initPromise = new Promise((r) => {
  _initResolve = r;
});

window.addEventListener("message", (e) => {
  if (e.source !== window.parent) return;
  const msg = e.data;
  if (!msg || typeof msg.type !== "string") return;

  if (msg.type === "pxc:init") {
    _initResolve(msg);
  } else if (msg.type === "pxc:event") {
    if (_activity) {
      _activity.onEvent(msg.name, JSON.parse(msg.value));
    } else {
      _pendingEvents.push(msg);
    }
  }
});

// Signal readiness; host responds with pxc:init
window.parent.postMessage({ type: "pxc:ready" }, "*");

const data = await _initPromise;

const root = document.getElementById("root");

// Shim adoptedStyleSheets on the root div — delegate to document,
// matching the behaviour of the shadow-DOM host element.
Object.defineProperty(root, "adoptedStyleSheets", {
  get() {
    return document.adoptedStyleSheets;
  },
  set(sheets) {
    document.adoptedStyleSheets = sheets;
  },
});

const activity = {
  element: root,
  context: data.context,
  state: data.state,
  permission: data.permission,

  getAssetUrl(path) {
    return `${data.assetBaseUrl}/${path}`;
  },

  async sendAction(name, value = "") {
    if (this.permission === "view") {
      console.warn("sendAction called in view mode — ignored:", name);
      return;
    }
    window.parent.postMessage({ type: "pxc:action", name, value }, "*");
  },

  onEvent(_name, _value) {
    // Overridden by ui.js setup()
  },
};

_activity = activity;

// Flush events that arrived before setup completed
for (const msg of _pendingEvents) {
  activity.onEvent(msg.name, JSON.parse(msg.value));
}
_pendingEvents.length = 0;

new ResizeObserver(() => {
  window.parent.postMessage(
    { type: "pxc:resize", height: document.documentElement.scrollHeight },
    "*",
  );
}).observe(root);

try {
  const mod = await import(data.uiSrc);
  if (typeof mod.setup === "function") {
    mod.setup(activity);
  }
} catch (err) {
  console.error("Failed to load activity UI:", err);
}
