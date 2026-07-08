"""Smoke tests for the libserver FastAPI app: auth gating + activity listing.

Does not exercise the xblock-callback adapters (HttpFieldStore/HttpFileStorage)
end-to-end — those need a live pxc-xblock internal API, covered separately.
"""

import json
import os

os.environ.setdefault("PXC_INTERNAL_SECRET", "test-secret")

import pytest
from fastapi.testclient import TestClient

from pxc.libserver.app import app

SECRET = os.environ["PXC_INTERNAL_SECRET"]


@pytest.fixture
def activities_dir(tmp_path, monkeypatch):
    activity = tmp_path / "hello"
    activity.mkdir()
    (activity / "manifest.json").write_text(
        json.dumps({"name": "hello", "ui": "ui.js"})
    )
    (activity / "ui.js").write_text("export function setup(a) {}")
    monkeypatch.setattr("pxc.libserver.config.ACTIVITIES_DIR", tmp_path)
    return tmp_path


@pytest.fixture
def client():
    return TestClient(app)


def test_activities_requires_secret(client):
    resp = client.get("/activities")
    assert resp.status_code == 401


def test_activities_rejects_wrong_secret(client):
    resp = client.get("/activities", headers={"X-PXC-Internal-Secret": "nope"})
    assert resp.status_code == 401


def test_activities_lists_bundle(client, activities_dir):
    resp = client.get("/activities", headers={"X-PXC-Internal-Secret": SECRET})
    assert resp.status_code == 200
    assert resp.json() == {"activities": ["hello"]}


def test_unknown_activity_state_is_404(client, activities_dir):
    resp = client.post(
        "/activities/nope/state",
        headers={"X-PXC-Internal-Secret": SECRET},
        json={
            "activity_id": "a1",
            "course_id": "c1",
            "user_id": "u1",
            "permission": "view",
        },
    )
    assert resp.status_code == 404


def test_healthz_needs_no_secret(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
