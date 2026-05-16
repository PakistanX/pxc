"""Short-lived HMAC tokens for cookie-free asset/storage access from sandboxed iframes."""

import hashlib
import hmac
import json
import logging
import os
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode

logger = logging.getLogger(__name__)

TOKEN_TTL_SECONDS = 3600


class TokenError(Exception):
    pass


def _secret() -> bytes:
    raw = os.environ.get("PXC_SIGNING_SECRET", "")
    if not raw:
        logger.warning("PXC_SIGNING_SECRET is not set; using insecure dev default")
        raw = "dev-insecure-default"
    return raw.encode()


def _b64e(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64d(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return urlsafe_b64decode(s + pad)


def make_token(
    *,
    activity_id: str,
    course_id: str,
    user_id: str,
    permission: str,
    ttl: int = TOKEN_TTL_SECONDS,
) -> str:
    """Return a signed token encoding the given claims, valid for `ttl` seconds."""
    claims = {
        "aid": activity_id,
        "cid": course_id,
        "uid": user_id,
        "p": permission,
        "exp": int(time.time()) + ttl,
    }
    payload = _b64e(json.dumps(claims, separators=(",", ":")).encode())
    sig = _b64e(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str) -> dict[str, str | int]:
    """Verify signature and expiry; return claims dict. Raises TokenError on failure."""
    try:
        payload, sig = token.split(".", 1)
    except ValueError as e:
        raise TokenError("malformed token") from e

    expected = _b64e(hmac.new(_secret(), payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(sig, expected):
        raise TokenError("bad signature")

    claims: dict[str, str | int] = json.loads(_b64d(payload))
    if int(claims["exp"]) < int(time.time()):
        raise TokenError("expired")
    return claims
