"use client";

export async function registerPxcActivity(): Promise<void> {
  if (typeof window === "undefined") return;
  if (customElements.get("pxc-activity")) return;

  // @ts-expect-error -- dynamic import of runtime-served JS module
  const { PXC } = await import(/* webpackIgnore: true */ "/static/js/pxc.js");

  class NotebookPXC extends PXC {
    _getWebsocketUrl(): string {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${location.host}/api/activity/${this.context.activity_id}/${this.permission}/ws`;
    }

    async _postAction(name: string, value: unknown): Promise<boolean> {
      const url = `/api/activity/${this.context.activity_id}/${this.permission}/actions`;
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify({ name, value }),
      });
      if (!response.ok) {
        console.error("POST action failed:", name, response.status);
        return false;
      }
      return true;
    }
  }

  customElements.define("pxc-activity", NotebookPXC as unknown as CustomElementConstructor);
}
