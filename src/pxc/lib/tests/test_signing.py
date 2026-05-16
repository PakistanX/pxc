import json
import time

import pytest

from pxc.lib.signing import TokenError, _b64e, make_token, verify_token


def _make() -> str:
    return make_token(activity_id="a1", course_id="c1", user_id="u1", permission="play")


def test_round_trip() -> None:
    claims = verify_token(_make())
    assert claims["aid"] == "a1"
    assert claims["cid"] == "c1"
    assert claims["uid"] == "u1"
    assert claims["p"] == "play"
    assert int(claims["exp"]) > int(time.time())


def test_tampered_payload_rejected() -> None:
    _payload, sig = _make().split(".", 1)
    evil_claims = {
        "aid": "other",
        "cid": "c1",
        "uid": "u1",
        "p": "edit",
        "exp": 9999999999,
    }
    evil_payload = _b64e(json.dumps(evil_claims, separators=(",", ":")).encode())
    with pytest.raises(TokenError, match="bad signature"):
        verify_token(f"{evil_payload}.{sig}")


def test_tampered_signature_rejected() -> None:
    payload, _sig = _make().split(".", 1)
    with pytest.raises(TokenError, match="bad signature"):
        verify_token(f"{payload}.AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")


def test_expired_token_rejected() -> None:
    token = make_token(
        activity_id="a1", course_id="c1", user_id="u1", permission="play", ttl=-1
    )
    with pytest.raises(TokenError, match="expired"):
        verify_token(token)


def test_malformed_token_rejected() -> None:
    with pytest.raises(TokenError, match="malformed"):
        verify_token("notavalidtoken")


def test_different_permissions() -> None:
    for perm in ("play", "edit", "view"):
        token = make_token(
            activity_id="a1", course_id="c1", user_id="u1", permission=perm
        )
        claims = verify_token(token)
        assert claims["p"] == perm
