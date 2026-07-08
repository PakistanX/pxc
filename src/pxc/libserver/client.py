"""Shared HTTP client for calling back into the pxc-xblock internal API.

Every host function that touches persistent state (fields, storage,
usernames) is a synchronous call made *from inside* a wasmtime host-function
callback, so this client is deliberately synchronous (httpx.Client, not
AsyncClient) — wasmtime has no notion of awaiting a coroutine mid-call.
"""

from typing import Any

import httpx

from pxc.libserver import config


class InternalApiError(Exception):
    """Raised when the xblock internal API returns an error response."""


_client: httpx.Client | None = None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            base_url=config.XBLOCK_INTERNAL_URL,
            timeout=config.CALLBACK_TIMEOUT,
            headers={"X-PXC-Internal-Secret": config.require_secret()},
        )
    return _client


def post(path: str, json: dict[str, Any]) -> Any:
    """POST to the xblock internal API and return the decoded JSON body.

    Raises:
        InternalApiError: On any non-2xx response.
    """
    resp = _get_client().post(path, json=json)
    if resp.status_code >= 400:
        raise InternalApiError(
            f"POST {path} -> {resp.status_code}: {resp.text[:500]}"
        )
    return resp.json()
