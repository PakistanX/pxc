"""Environment-based configuration for the PXC lib-server.

No Django/Tutor assumptions here — this service is meant to run as a plain
standalone process (systemd unit, bare `uvicorn`, container, whatever) next to
a devstack-based Open edX install. All configuration is env vars so it can be
wired up however the platform is deployed.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Loads a `.env` file (if present) into os.environ *before* the os.environ.get()
# calls below run. Searches the current working directory and walks upward —
# put `.env` wherever you launch uvicorn from (or any parent of it). Does NOT
# override variables already set in the real environment (e.g. by systemd's
# EnvironmentFile= or a shell export), so a `.env` is a fallback/dev
# convenience, not a way to force a value over what's already exported.
load_dotenv()

# Base URL of the pxc-xblock internal callback API (Django, running inside
# LMS/CMS). Host functions that touch persistent state (fields, storage,
# usernames) call back here — see internal_api.py in pxc.xblock.
XBLOCK_INTERNAL_URL: str = os.environ.get(
    "PXC_XBLOCK_INTERNAL_URL", "http://localhost:18000/pxc/internal"
).rstrip("/")

# Shared secret sent as `X-PXC-Internal-Secret` on every call in *both*
# directions (xblock -> libserver, libserver -> xblock). Must match the
# PXC_INTERNAL_SECRET configured on the xblock side. There is no safe default:
# an empty secret is rejected at startup so a misconfigured deployment fails
# loudly instead of running with auth disabled.
INTERNAL_SECRET: str = os.environ.get("PXC_INTERNAL_SECRET", "")

# Directory containing activity bundles (manifest.json/sandbox.wasm/ui.js/
# assets), one subdirectory per activity slug — same layout as
# pxc.xblock's `samples/` directory. In a devstack checkout you can point
# this directly at that directory since both processes share the filesystem;
# in a real deployment, ship the same bundle contents into this service's
# image/volume instead of duplicating them by hand.
ACTIVITIES_DIR: Path = Path(
    os.environ.get(
        "PXC_ACTIVITIES_DIR",
        str(Path(__file__).resolve().parents[1] / "xblock" / "samples"),
    )
)

# httpx timeout (seconds) for callbacks to the xblock internal API.
CALLBACK_TIMEOUT: float = float(os.environ.get("PXC_CALLBACK_TIMEOUT", "10"))

# Whether /activities/upload is allowed to run componentize-py against an
# uploaded sandbox.py (arbitrary-code-execution-at-build-time). Off by
# default — a deliberately secure-by-default flag, not just a convenience
# one. Uploading an *already-built* sandbox.wasm bundle (no code execution,
# just validation + a file copy) always works regardless of this setting.
# Set PXC_ENABLE_ACTIVITY_BUILD=1 to allow server-side builds.
ENABLE_ACTIVITY_BUILD: bool = os.environ.get("PXC_ENABLE_ACTIVITY_BUILD", "").lower() in (
    "1",
    "true",
    "yes",
)


def require_secret() -> str:
    if not INTERNAL_SECRET:
        raise RuntimeError(
            "PXC_INTERNAL_SECRET is not set. Refusing to start with an "
            "unauthenticated internal callback channel."
        )
    return INTERNAL_SECRET
