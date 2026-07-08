"""Tests for the activity upload/build pipeline (zip -> validate -> [build] -> install)."""

import io
import json
import zipfile
from pathlib import Path

import pytest

from pxc.libserver.build import BuildError
from pxc.libserver.upload import UploadError, install_activity_bundle

SAMPLES_DIR = Path(__file__).resolve().parents[4] / "samples"


def _zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for arcname, content in files.items():
            zf.writestr(arcname, content)
    return buf.getvalue()


def _prebuilt_mcq_zip():
    files = {}
    for name in ("manifest.json", "ui.js", "sandbox.wasm"):
        files[name] = (SAMPLES_DIR / "mcq" / name).read_bytes()
    return files


@pytest.fixture(autouse=True)
def activities_dir(tmp_path, monkeypatch):
    monkeypatch.setattr("pxc.libserver.config.ACTIVITIES_DIR", tmp_path)
    return tmp_path


def test_install_prebuilt_bundle(activities_dir):
    zip_bytes = _zip_bytes(_prebuilt_mcq_zip())
    slug = install_activity_bundle(zip_bytes)
    assert slug == "mcq"
    assert (activities_dir / "mcq" / "manifest.json").is_file()
    assert (activities_dir / "mcq" / "sandbox.wasm").is_file()


def test_rejects_missing_manifest(activities_dir):
    zip_bytes = _zip_bytes({"ui.js": b"export function setup(a) {}"})
    with pytest.raises(UploadError, match="manifest.json"):
        install_activity_bundle(zip_bytes)


def test_rejects_invalid_manifest_json(activities_dir):
    zip_bytes = _zip_bytes({"manifest.json": b"not json", "ui.js": b""})
    with pytest.raises(UploadError, match="invalid"):
        install_activity_bundle(zip_bytes)


def test_rejects_bad_slug(activities_dir):
    manifest = json.dumps({"name": "../escape", "ui": "ui.js"})
    zip_bytes = _zip_bytes({"manifest.json": manifest, "ui.js": b""})
    with pytest.raises(UploadError, match="must match"):
        install_activity_bundle(zip_bytes)


def test_rejects_missing_ui(activities_dir):
    manifest = json.dumps({"name": "noui", "ui": "ui.js"})
    zip_bytes = _zip_bytes({"manifest.json": manifest})
    with pytest.raises(UploadError, match="ui.js"):
        install_activity_bundle(zip_bytes)


def test_rejects_build_when_disabled_by_default(activities_dir):
    """PXC_ENABLE_ACTIVITY_BUILD is off unless explicitly set — a missing
    prebuilt .wasm must fail with a "build disabled" message, not attempt
    componentize-py at all."""
    manifest = json.dumps({"name": "nowasm", "ui": "ui.js", "sandbox": "sandbox.wasm"})
    zip_bytes = _zip_bytes({"manifest.json": manifest, "ui.js": b""})
    with pytest.raises(UploadError, match="server-side building is disabled"):
        install_activity_bundle(zip_bytes)


@pytest.fixture
def build_enabled(monkeypatch):
    monkeypatch.setattr("pxc.libserver.config.ENABLE_ACTIVITY_BUILD", True)


def test_rejects_missing_sandbox_and_source(activities_dir, build_enabled):
    manifest = json.dumps({"name": "nowasm", "ui": "ui.js", "sandbox": "sandbox.wasm"})
    zip_bytes = _zip_bytes({"manifest.json": manifest, "ui.js": b""})
    with pytest.raises(UploadError, match="sandbox.py"):
        install_activity_bundle(zip_bytes)


def test_rejects_python_source_without_wit(activities_dir, build_enabled):
    manifest = json.dumps({"name": "nowit", "ui": "ui.js", "sandbox": "sandbox.wasm"})
    zip_bytes = _zip_bytes(
        {"manifest.json": manifest, "ui.js": b"", "sandbox.py": b"# stub"}
    )
    with pytest.raises(UploadError, match="pxc.wit"):
        install_activity_bundle(zip_bytes)


def test_rejects_zip_slip_path_traversal(activities_dir):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.txt", b"pwned")
    with pytest.raises(UploadError, match="Unsafe path"):
        install_activity_bundle(buf.getvalue())


def test_rejects_not_a_zip(activities_dir):
    with pytest.raises(UploadError, match="valid zip"):
        install_activity_bundle(b"definitely not a zip")


def test_builds_python_source_via_componentize_py(activities_dir, build_enabled):
    """End-to-end: uncompiled Python sandbox source gets built server-side."""
    files = {
        "manifest.json": (SAMPLES_DIR / "markdown" / "manifest.json").read_bytes(),
        "pxc.wit": (SAMPLES_DIR / "markdown" / "pxc.wit").read_bytes(),
        "sandbox.py": (SAMPLES_DIR / "markdown" / "server.py").read_bytes(),
        "ui.js": (SAMPLES_DIR / "markdown" / "ui.js").read_bytes(),
    }
    slug = install_activity_bundle(_zip_bytes(files))
    assert slug == "markdown"
    assert (activities_dir / "markdown" / "sandbox.wasm").is_file()


def test_build_error_surfaces_missing_dependency(activities_dir, build_enabled):
    """A sandbox.py importing something not installed fails with a readable BuildError."""
    manifest = json.dumps({"name": "baddep", "ui": "ui.js", "sandbox": "sandbox.wasm"})
    wit = (SAMPLES_DIR / "markdown" / "pxc.wit").read_bytes()
    files = {
        "manifest.json": manifest,
        "pxc.wit": wit,
        "sandbox.py": b"import this_module_does_not_exist_anywhere\n",
        "ui.js": b"",
    }
    with pytest.raises(BuildError):
        install_activity_bundle(_zip_bytes(files))
