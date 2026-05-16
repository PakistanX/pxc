// XBlockPXC — HTTP transport variant of <pxc-activity> for Open edX.
//
// Loaded by the pxc-xblock fragment after pxc.js. Overrides the lifecycle to
// send actions via HTTP POST and poll for cross-user events via GET, instead
// of using the WebSocket transport that pxc.js's base PXC class ships.
//
// Reads three extra data-* attributes off <pxc-activity>:
//   data-action-url       POST endpoint for actions
//   data-events-url       GET endpoint for the event poll
//   data-events-cursor    Initial PendingEvent id to poll after (set by the
//                         server at fragment render time so first-time clients
//                         skip the backlog and start at "now").

const POLL_INTERVAL_MS = 5000;

// All HTTP traffic goes through jQuery's $.ajax rather than native fetch:
// Open edX guarantees jQuery on every page that loads this bundle, and its
// global $.ajaxSetup attaches X-CSRFToken from the csrftoken cookie to every
// POST automatically — Django's CSRF middleware rejects POSTs without it.

export class XBlockPXC extends PXC {
  constructor() {
    super();
    this._actionUrl = null;
    this._eventsUrl = null;
    this._eventsCursor = 0;
    this._pollInterval = null;
  }

  async connectedCallback() {
    this._initFromAttrs();

    this._actionUrl = this.getAttribute("data-action-url");
    this._eventsUrl = this.getAttribute("data-events-url");
    this._eventsCursor = parseInt(
      this.getAttribute("data-events-cursor") || "0",
      10,
    );

    this._initShadow();
    this.render();
    const src = this.getAttribute("data-src");
    if (src) {
      await this._loadScript(src);
    }
    this._startPolling();
  }

  async sendAction(name, value = "") {
    if (this.permission === "view") {
      console.warn("sendAction called in view mode — ignored:", name);
      return;
    }
    let data;
    try {
      data = await $.ajax({
        url: this._actionUrl,
        method: "POST",
        contentType: "application/json",
        data: JSON.stringify({ name, value, permission: this.permission }),
      });
    } catch (xhr) {
      console.error("Action failed:", name, xhr.status);
      return;
    }
    if (data.cursor !== undefined) {
      this._eventsCursor = data.cursor;
    }
    for (const event of data.events || []) {
      this.onEvent(event.name, JSON.parse(event.value));
    }
  }

  _startPolling() {
    this._pollInterval = setInterval(() => this._pollEvents(), POLL_INTERVAL_MS);
  }

  async _pollEvents() {
    if (!this._eventsUrl) return;
    let data;
    try {
      data = await $.ajax({
        url: this._eventsUrl,
        method: "GET",
        data: { since: this._eventsCursor },
      });
    } catch (xhr) {
      console.error("Polling failed:", xhr.status);
      return;
    }
    if (data.cursor !== undefined) {
      this._eventsCursor = data.cursor;
    }
    for (const event of data.events || []) {
      this.onEvent(event.name, JSON.parse(event.value));
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._pollInterval) {
      clearInterval(this._pollInterval);
      this._pollInterval = null;
    }
  }
}
