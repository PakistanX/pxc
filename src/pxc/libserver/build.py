"""Server-side build of uploaded Python sandbox source via componentize-py.

Only Python sandboxes are supported for server-side builds — JS sandboxes
need a bundling step (esbuild/webpack) plus npm dependency resolution that's
a much bigger, network-fetching attack surface to run against arbitrary
uploads. Activities with a JS sandbox must still be pre-built locally and
uploaded with ``sandbox.wasm`` already present (see upload.py).

Uploaded Python sandbox source may only import the standard library plus
whatever's already installed in this process's environment (pxc-lib's own
deps, plus anything the platform operator has additionally installed) —
there is no per-upload dependency installation. componentize-py needs those
dependencies importable at build time (it actually imports and introspects
the module), so missing ones surface as a build error, not a runtime one.
"""

import shutil
import site
import subprocess
import sys
from pathlib import Path

# componentize-py needs the app module name to differ from any WIT world it
# targets ("activity", per every existing sample's Makefile convention).
SANDBOX_MODULE_NAME = "sandbox"
WIT_WORLD_NAME = "activity"
BUILD_TIMEOUT_SECONDS = 120


class BuildError(Exception):
    """Raised when componentize-py fails to build a sandbox. ``str(e)`` is
    the combined stdout/stderr, safe to show to the uploading course staff
    member (it's their own build's compiler output)."""


def _componentize_py_executable() -> str:
    """Resolve the componentize-py console script next to the running
    interpreter (same venv/install), falling back to PATH lookup.

    ``python -m componentize_py`` doesn't work — the package has no
    ``__main__.py``; it only ships a console-script entry point.
    """
    candidate = Path(sys.executable).with_name("componentize-py")
    if candidate.exists():
        return str(candidate)
    return "componentize-py"


def build_python_sandbox(staging_dir: Path, wit_path: Path, output_path: Path) -> None:
    """Build ``sandbox.py`` (in ``staging_dir``) into a WASM component.

    Raises:
        BuildError: If the build fails or times out. Message is the
            componentize-py output (compiler errors, missing imports, etc).
    """
    # --wit-path/--world are top-level flags; --python-path/--output belong
    # to the `componentize` subcommand — order matters to the CLI parser.
    python_paths = [str(staging_dir)] + list(site.getsitepackages())
    cmd = [
        _componentize_py_executable(),
        "--wit-path",
        str(wit_path),
        "--world",
        WIT_WORLD_NAME,
        "componentize",
        "--output",
        str(output_path),
    ]
    for path in python_paths:
        cmd += ["--python-path", path]
    cmd.append(SANDBOX_MODULE_NAME)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(staging_dir),
            capture_output=True,
            text=True,
            timeout=BUILD_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as e:
        raise BuildError(
            "Build timed out after {0}s".format(BUILD_TIMEOUT_SECONDS)
        ) from e
    if result.returncode != 0:
        raise BuildError(
            "componentize-py failed (exit {0}):\n{1}\n{2}".format(
                result.returncode, result.stdout, result.stderr
            )
        )
    if not output_path.exists():
        raise BuildError("componentize-py reported success but produced no output file")


def cleanup(staging_dir: Path) -> None:
    """Remove a staging directory, ignoring errors (best-effort cleanup)."""
    shutil.rmtree(staging_dir, ignore_errors=True)
