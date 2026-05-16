"""Tests for HMAC token auth on asset/storage endpoints (sandboxed iframe support)."""

import json
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pxc.demo import constants
from pxc.demo.app import app
from pxc.lib.signing import make_token


def _make_token(**overrides: str) -> str:
    return make_token(
        activity_id=overrides.get("activity_id", "test-activity"),
        course_id=overrides.get("course_id", "democourse"),
        user_id=overrides.get("user_id", "alice"),
        permission=overrides.get("permission", "play"),
    )


@pytest.fixture(name="samples_dir")
def fixtures_samples_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory() as tmpdir:
        samples_path = Path(tmpdir)
        activity_path = samples_path / "test-activity"
        activity_path.mkdir()
        manifest: dict[str, Any] = {
            "name": "test-activity",
            "ui": "ui.js",
            "capabilities": {},
            "assets": ["asset.txt"],
        }
        (activity_path / "manifest.json").write_text(json.dumps(manifest))
        (activity_path / "ui.js").write_text("export function setup() {}")
        (activity_path / "asset.txt").write_text("hello")
        monkeypatch.setattr(constants, "SAMPLES_DIR", samples_path)
        yield samples_path


@pytest.fixture(name="client")
def fixtures_client(samples_dir: Path) -> TestClient:  # pylint: disable=unused-argument
    return TestClient(app, raise_server_exceptions=True)


class TestIframeBootstrap:
    def test_iframe_page_returns_html(self, client: TestClient) -> None:
        r = client.get("/_pxc/iframe")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "/_pxc/iframe.js" in r.text

    def test_iframe_js_has_cors(self, client: TestClient) -> None:
        r = client.get("/_pxc/iframe.js")
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "*"


class TestAssetTokenAuth:
    def test_valid_token_returns_asset(self, client: TestClient) -> None:
        tok = _make_token()
        r = client.get(f"/_pxc/t/{tok}/a/test-activity/asset.txt")
        assert r.status_code == 200
        assert r.text == "hello"

    def test_valid_token_has_cors_headers(self, client: TestClient) -> None:
        tok = _make_token()
        r = client.get(f"/_pxc/t/{tok}/a/test-activity/asset.txt")
        assert r.headers.get("access-control-allow-origin") == "null"
        assert "Origin" in r.headers.get("vary", "")

    def test_no_token_no_cookie_returns_200_for_first_simulated_user(
        self, client: TestClient
    ) -> None:
        # Cookie route falls back to first simulated user when no cookie set
        r = client.get("/a/test-activity/asset.txt")
        assert r.status_code == 200

    def test_expired_token_rejected(self, client: TestClient) -> None:
        token = make_token(
            activity_id="test-activity",
            course_id="democourse",
            user_id="alice",
            permission="play",
            ttl=-1,
        )
        r = client.get(f"/_pxc/t/{token}/a/test-activity/asset.txt")
        assert r.status_code == 401

    def test_bad_signature_rejected(self, client: TestClient) -> None:
        payload, _ = _make_token().split(".", 1)
        r = client.get(f"/_pxc/t/{payload}.BADSIG/a/test-activity/asset.txt")
        assert r.status_code == 401

    def test_mismatched_activity_rejected(self, client: TestClient) -> None:
        token = _make_token(activity_id="other-activity")
        r = client.get(f"/_pxc/t/{token}/a/test-activity/asset.txt")
        assert r.status_code == 403


class TestUiJsTokenAuth:
    def test_valid_token_serves_ui_js(self, client: TestClient) -> None:
        tok = _make_token()
        r = client.get(f"/_pxc/t/{tok}/a/test-activity/ui.js")
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "null"
