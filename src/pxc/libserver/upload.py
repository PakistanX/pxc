"""Install an uploaded activity bundle (zip) into PXC_ACTIVITIES_DIR.

Two supported bundle shapes:
  - Pre-built: manifest.json + ui.js + <the .wasm file the manifest's
    "sandbox" key names> [+ assets]. No build step, just validated and
    installed as-is. Works for both Python- and JS-sandbox activities.
  - Python source: same, but a "sandbox.py" + "pxc.wit" instead of the
    compiled .wasm — built here via componentize-py (see build.py). JS
    source is not built server-side (see build.py's docstring).

Not exposed to browsers directly — reached only via pxc-xblock's Studio-only
`upload_activity` handler (course-author permission gated), itself behind
this service's usual internal-secret auth.
"""

import io
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from pxc.lib.manifest_types import PxcActivityManifest
from pxc.libserver import config
from pxc.libserver.build import BuildError, build_python_sandbox, cleanup

_SLUG_RE = re.compile(r"^[a-zA-Z0-9_-]+$")
MAX_UNCOMPRESSED_BYTES = 100 * 1024 * 1024  # 100MB — generous for a wasm bundle
MAX_ZIP_ENTRIES = 2000


class UploadError(Exception):
    """Raised for any invalid/unsafe/failed upload. Message is safe to show
    to the uploading course staff member."""


def _safe_extract(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract a zip, rejecting path traversal and decompression-bomb-ish input."""
    names = zf.namelist()
    if len(names) > MAX_ZIP_ENTRIES:
        raise UploadError("Zip has too many entries ({0})".format(len(names)))
    total = 0
    for info in zf.infolist():
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise UploadError("Zip is too large uncompressed")
        name = info.filename
        # Reject absolute paths and any ".." segment (zip-slip).
        if name.startswith("/") or name.startswith("\\"):
            raise UploadError("Unsafe path in zip: {0!r}".format(name))
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise UploadError("Unsafe path in zip: {0!r}".format(name))
    zf.extractall(str(dest))


def _load_manifest(bundle_dir: Path) -> PxcActivityManifest:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        raise UploadError("Zip has no manifest.json at its root")
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        return PxcActivityManifest.model_validate_json(raw)
    except ValueError as e:
        # Covers both json.JSONDecodeError and pydantic's ValidationError
        # (a ValueError subclass in pydantic v2).
        raise UploadError("manifest.json is invalid: {0}".format(e)) from e


def install_activity_bundle(zip_bytes: bytes) -> str:
    """Validate, (if needed) build, and install an uploaded activity bundle.

    Returns the installed activity's slug.

    Raises:
        UploadError: Bad zip, bad manifest, bad slug, or missing sandbox
            source/binary.
        BuildError: componentize-py failed (only for Python-source bundles).
    """
    staging_root = Path(tempfile.mkdtemp(prefix="pxc-upload-"))
    try:
        extract_dir = staging_root / "bundle"
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                _safe_extract(zf, extract_dir)
        except zipfile.BadZipFile as e:
            raise UploadError("Not a valid zip file") from e

        manifest = _load_manifest(extract_dir)
        slug = manifest.name
        if not _SLUG_RE.match(slug):
            raise UploadError(
                "Activity name {0!r} must match {1}".format(slug, _SLUG_RE.pattern)
            )

        if manifest.sandbox is not None:
            wasm_rel = manifest.sandbox
            wasm_path = extract_dir / wasm_rel
            if not wasm_path.is_file():
                if not config.ENABLE_ACTIVITY_BUILD:
                    raise UploadError(
                        "manifest declares sandbox={0!r} but the zip has no "
                        "pre-built copy of it, and server-side building is "
                        "disabled on this deployment (PXC_ENABLE_ACTIVITY_BUILD "
                        "is not set) — upload a bundle with the .wasm already "
                        "built instead".format(wasm_rel)
                    )
                py_source = extract_dir / "sandbox.py"
                wit_path = extract_dir / "pxc.wit"
                if not py_source.is_file():
                    raise UploadError(
                        "manifest declares sandbox={0!r} but the zip has neither "
                        "that file nor a buildable sandbox.py".format(wasm_rel)
                    )
                if not wit_path.is_file():
                    raise UploadError(
                        "sandbox.py present but no pxc.wit — every bundle must "
                        "include its own WIT world definition (see samples/ for "
                        "reference)"
                    )
                build_python_sandbox(extract_dir, wit_path, wasm_path)

        if not (extract_dir / manifest.ui).is_file():
            raise UploadError(
                "manifest declares ui={0!r} but the zip has no such file".format(
                    manifest.ui
                )
            )

        dest = config.ACTIVITIES_DIR / slug
        config.ACTIVITIES_DIR.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(extract_dir), str(dest))
        return slug
    finally:
        cleanup(staging_root)
