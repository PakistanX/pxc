// ---- IndexedDB helpers ----

let _dbPromise = null;

function _openDB() {
  if (!_dbPromise) {
    _dbPromise = new Promise((resolve, reject) => {
      const req = indexedDB.open("pxc", 1);
      req.onupgradeneeded = () => {
        const store = req.result.createObjectStore("pending-actions", {
          autoIncrement: true,
        });
        store.createIndex("owner", ["activityId", "userId"]);
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }
  return _dbPromise;
}

function _idbReq(req) {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function _idbTxDone(tx) {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

// ---- PXC custom element ----

export class PXC extends HTMLElement {
  constructor() {
    super();
    this.context = {};
    this.state = {};
    this.permission = "view";
    this._ws = null;
    this._iframe = null;
    this._reconnectDelay = 500;
    this._flushing = false;
    this._flushAgain = false;
  }

  // Parse the data-* attributes common to every transport. Subclasses call
  // this from their own connectedCallback before reading transport-specific
  // attrs.
  _initFromAttrs() {
    const contextAttr = this.getAttribute("data-context");
    if (contextAttr) {
      this.context = JSON.parse(contextAttr);
    }

    this._wsUrl = this.getAttribute("data-ws-url");
    this._assetBaseUrl = this.getAttribute("data-asset-base-url");
    this._pxcToken = this.getAttribute("data-pxc-token");

    const stateAttr = this.getAttribute("data-state");
    if (stateAttr) {
      this.state = JSON.parse(stateAttr);
    }

    const permissionAttr = this.getAttribute("data-permission");
    if (permissionAttr) {
      this.permission = permissionAttr;
    }
  }

  async connectedCallback() {
    this._initFromAttrs();

    const embedMode = this.getAttribute("embed") || "shadow";

    if (embedMode === "native") {
      this._initIframe();
      await _openDB();
      this._connectWebSocket();
    } else {
      this._initShadow();
      this.render();
      await _openDB();
      this._connectWebSocket();
      const src = this.getAttribute("data-src");
      if (src) {
        this._loadScript(src);
      }
    }
  }

  _initShadow() {
    this.element = this.attachShadow({ mode: "closed" });
    var sheet = new CSSStyleSheet();
    // TODO how to pass CSS from the host to the shadow element? Should this be part of the standard?
    sheet.replaceSync(`
      :host {
          display: block;
          padding: 1em;
          border: 1px solid #ccc;
        }
    `);
    this.element.adoptedStyleSheets = [sheet];
  }

  _initIframe() {
    const iframe = document.createElement("iframe");
    iframe.setAttribute("sandbox", "allow-scripts allow-forms");
    iframe.src = "/_pxc/iframe";
    iframe.style.cssText = "width:100%;border:none;display:block;";
    this.appendChild(iframe);
    this._iframe = iframe;

    window.addEventListener("message", (e) => {
      if (!this._iframe || e.source !== this._iframe.contentWindow) return;
      const msg = e.data;
      if (!msg || typeof msg.type !== "string") return;

      if (msg.type === "pxc:ready") {
        this._sendIframeInit();
      } else if (msg.type === "pxc:action") {
        this._pushAction({
          action: msg.name,
          value: msg.value,
          permission: this.permission,
        });
      } else if (msg.type === "pxc:resize") {
        iframe.style.height = msg.height + "px";
      }
    });
  }

  _sendIframeInit() {
    if (!this._iframe) return;
    const token = this._pxcToken;
    let assetBaseUrl, uiSrc;
    if (token) {
      const id = this.context.activity_id;
      assetBaseUrl = `${window.location.origin}/_pxc/t/${token}/a/${id}`;
      uiSrc = `${assetBaseUrl}/ui.js`;
    } else {
      assetBaseUrl = new URL(
        this._assetBaseUrl || `/a/${this.context.activity_id}`,
        window.location.href,
      ).href;
      uiSrc = this.getAttribute("data-src");
    }
    this._iframe.contentWindow.postMessage(
      {
        type: "pxc:init",
        context: this.context,
        state: this.state,
        permission: this.permission,
        uiSrc,
        assetBaseUrl,
      },
      "*",
    );
  }

  render() {
    this.element.innerHTML = "Empty activity";
  }

  _connectWebSocket() {
    // Cookies are sent automatically on the WebSocket handshake
    this._ws = new WebSocket(this._getWebsocketUrl());
    this._ws.onopen = () => {
      this._reconnectDelay = 500;
      this._flushQueue();
      this._setOfflineBanner(false);
    };
    this._ws.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (this._iframe) {
        this._iframe.contentWindow.postMessage(
          { type: "pxc:event", name: event.name, value: event.value },
          "*",
        );
      } else {
        this.onEvent(event.name, JSON.parse(event.value));
      }
    };
    this._ws.onclose = () => {
      if (this.isConnected) {
        // Only attempt to reconnect when the activity is in the DOM
        this._setOfflineBanner(true);
        this._scheduleReconnect();
      }
    };
  }

  _getWebsocketUrl() {
    if (this._wsUrl) return this._wsUrl;
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${location.host}/api/activity/${this.context.activity_id}/ws`;
  }

  _setOfflineBanner(visible) {
    window.dispatchEvent(new CustomEvent("pxc:connection", {
      detail: { connected: !visible },
    }));
  }

  _scheduleReconnect() {
    setTimeout(() => {
      this._reconnectDelay = Math.min(this._reconnectDelay * 2, 2000);
      this._connectWebSocket();
    }, this._reconnectDelay);
  }

  async _flushQueue() {
    if (this._flushing) {
      this._flushAgain = true;
      return;
    }
    this._flushing = true;
    try {
      do {
        this._flushAgain = false;

        const db = await _openDB();
        const key = [this.context.activity_id, this.context.user_id];

        // Read all pending records in one shot (no await between IDB operations)
        const tx = db.transaction("pending-actions", "readonly");
        const index = tx.objectStore("pending-actions").index("owner");
        const [records, primaryKeys] = await Promise.all([
          _idbReq(index.getAll(key)),
          _idbReq(index.getAllKeys(key)),
        ]);

        // Send via WS, falling back to HTTP POST for large payloads.
        // Uvicorn's websockets implementation caps incoming frames at 1 MiB by
        // default; a frame above that ceiling closes the connection with code
        // 1006 before the server can read it. The POST actions endpoint has no
        // such limit, so we route anything approaching the cap through HTTP.
        const WS_PAYLOAD_MAX = 512 * 1024;
        const sentKeys = [];
        for (let i = 0; i < records.length; i++) {
          const { action, value, permission } = records[i];
          const payload = JSON.stringify({ action, value, permission });
          if (payload.length > WS_PAYLOAD_MAX) {
            const ok = await this._postAction(action, value);
            if (!ok) break;
          } else {
            if (this._ws.readyState !== WebSocket.OPEN) break;
            this._ws.send(payload);
          }
          sentKeys.push(primaryKeys[i]);
        }

        // Delete sent records
        if (sentKeys.length > 0) {
          const delTx = db.transaction("pending-actions", "readwrite");
          const store = delTx.objectStore("pending-actions");
          for (const pk of sentKeys) {
            store.delete(pk);
          }
          await _idbTxDone(delTx);
        }
      } while (this._flushAgain);
    } finally {
      this._flushing = false;
    }
  }

  async _loadScript(url) {
    try {
      const module = await import(url);
      if (typeof module.setup === "function") {
        module.setup(this);
      }
    } catch (error) {
      console.error("Failed to load activity script:", error);
    }
  }

  async sendAction(name, value = "") {
    if (this.permission === "view") {
      console.warn("sendAction called in view mode — ignored:", name);
      return;
    }
    await this._pushAction({ action: name, value, permission: this.permission });
  }

  async _postAction(name, value) {
    const url = `/api/activity/${this.context.activity_id}/actions/${encodeURIComponent(name)}`;
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(value),
    });
    if (!response.ok) {
      console.error("POST action failed:", name, response.status);
      return false;
    }
    return true;
  }

  async _pushAction(action) {
    const db = await _openDB();
    const record = {
      activityId: this.context.activity_id,
      userId: this.context.user_id,
      ...action,
    };
    const tx = db.transaction("pending-actions", "readwrite");
    tx.objectStore("pending-actions").add(record);
    await _idbTxDone(tx);
    if (this._ws.readyState === WebSocket.OPEN) {
      this._flushQueue();
    }
  }

  getAssetUrl(path) {
    if (this._assetBaseUrl) return `${this._assetBaseUrl}/${path}`;
    return new URL(`/a/${this.context.activity_id}/${path}`, location.href).href;
  }

  onEvent(name, value) {
    // Default no-op. Override in ui.js to handle events.
  }

  disconnectedCallback() {
    if (this._ws) {
      this._ws.close();
    }
    this._setOfflineBanner(false);
  }
}
