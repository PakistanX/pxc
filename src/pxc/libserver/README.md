# PXC Lib Server

Standalone FastAPI service that hosts `pxc-lib`'s `ActivityRuntime` and the
wasmtime WASM sandbox. Exists so this code can run on a modern Python
(3.11+, required by `wasmtime` + `pydantic>=2`) independently of whatever
Python your LMS/CMS process runs — see [pxc-xblock](../xblock/README.md) for
the Open edX side of this split.

## Why this exists

`pxc-xblock` used to import `pxc-lib` directly and instantiate
`ActivityRuntime` in-process on every handler call. That's fine when the
XBlock's Django process can run Python 3.11+, but not every Open edX install
can (e.g. an older Juniper-based devstack pinned to an older Python). This
service extracts the `pxc-lib`-dependent code into its own process so the
two can be upgraded independently.

## What lives where after the split

| Concern | Lives in |
|---|---|
| Manifest parsing, capability/action/event/field validation | **here** (`pxc-lib`) |
| WASM sandbox execution (wasmtime) | **here** |
| Activity bundles (manifest.json/sandbox.wasm/ui.js/assets) | **here** (`PXC_ACTIVITIES_DIR`) |
| Field storage (`FieldEntry`/`FieldLogEntry` rows) | pxc-xblock (Django ORM) — this service calls back over HTTP |
| File storage (S3 via Django `default_storage`) | pxc-xblock — this service calls back over HTTP |
| Username resolution | pxc-xblock (Django `User` model) — callback |
| Grading (`report_*`) | **here** (buffered as `GradeEvent`s) — actual publishing happens in pxc-xblock's `action` handler via `self.runtime.publish(...)`, since only that process has XBlock runtime/usage context. See `pxc.lib.runtime.GradeEvent` for the completion/grade payload mapping. |

Every host function that touches persistent state is therefore a **synchronous
HTTP callback** from inside a wasmtime host-function call, back into
pxc-xblock's internal API (`pxc.xblock.internal_api`, mounted at
`/pxc/internal/...` in both LMS and CMS). This keeps S3 credentials and DB
access in exactly one place (the LMS/CMS Django settings you already have),
at the cost of extra network hops per field/storage operation. See
[field_store.py](./field_store.py) / [file_storage.py](./file_storage.py).

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `PXC_XBLOCK_INTERNAL_URL` | `http://localhost:18000/pxc/internal` | Base URL of pxc-xblock's internal callback API |
| `PXC_INTERNAL_SECRET` | *(required, no default)* | Shared secret sent as `X-PXC-Internal-Secret` in **both** directions. Must match the xblock side. Service refuses to start requests without it. |
| `PXC_ACTIVITIES_DIR` | `../xblock/samples` (repo-relative) | Directory of activity bundles, one subdir per slug. In a devstack checkout with a shared filesystem you can point this straight at `pxc-xblock`'s `samples/` dir; in a real deployment, ship the bundle contents into this service's image/volume instead. |
| `PXC_CALLBACK_TIMEOUT` | `10` | Seconds before a callback to pxc-xblock times out |
| `PXC_ENABLE_ACTIVITY_BUILD` | *(unset = off)* | Set to `1`/`true`/`yes` to allow `/activities/upload` to run `componentize-py` against an uploaded `sandbox.py`. **Off by default** — a secure-by-default flag, not a convenience one (see "Uploading new activities" below). Uploading an already-built `sandbox.wasm` bundle works either way; this only gates server-side code execution. |

## Running

```bash
pip install -e src/pxc/lib -e src/pxc/libserver
PXC_INTERNAL_SECRET=change-me \
PXC_XBLOCK_INTERNAL_URL=http://localhost:18000/pxc/internal \
  uvicorn pxc.libserver.app:app --host 0.0.0.0 --port 9760
```

This is a **plain standalone process** — no Tutor/docker-compose assumptions.
Run it under systemd, a container, a second devstack terminal, whatever fits
your deployment. Point `pxc-xblock`'s `PXC_LIBSERVER_URL` Django setting at
wherever it ends up listening.

## Endpoints

All routes except `/healthz` require `X-PXC-Internal-Secret`.

- `GET /activities` — list bundled activity slugs
- `POST /activities/{slug}/state` — `get_state()`
- `POST /activities/{slug}/action` — `on_action()` + buffered events
- `GET /activities/{slug}/ui` — the activity's `ui.js`
- `GET /activities/{slug}/asset/{path}` — a manifest-declared asset
- `POST /activities/{slug}/storage/read` — a storage-capability file read (used by pxc-xblock's browser-facing `storage` handler, and internally for capability/scope enforcement)
- `POST /activities/upload` — install a new activity from an uploaded zip (see below)

## Uploading new activities (`POST /activities/upload`)

Superusers can add activities without a separate deploy, via a Studio
"Upload new activity" widget (pxc-xblock's `upload_activity` handler —
gated on Django `is_superuser`, deliberately stricter than the
course-author permission used for everything else in Studio, since this can
run arbitrary Python source through a compiler) that proxies straight to
this endpoint. See [upload.py](./upload.py) / [build.py](./build.py).

**Bundle format** — a zip containing:
- `manifest.json` (required) — `name` becomes the installed slug; must match
  `^[a-zA-Z0-9_-]+$`.
- `ui.js` (or whatever `manifest.ui` names).
- The sandbox, in one of two forms:
  - **Pre-built**: the `.wasm` file `manifest.sandbox` names, already
    compiled (works for both Python- and JS-sandbox activities — build
    locally with the usual `make build`, same as `samples/*/Makefile`, then
    zip the result). **No code runs server-side for this path** — just zip
    validation, manifest validation, and a file copy. Works regardless of
    `PXC_ENABLE_ACTIVITY_BUILD`.
  - **Python source**: a `sandbox.py` (a `wit_world.WitWorld` subclass, same
    shape as `samples/markdown/server.py`) plus the bundle's own `pxc.wit`
    (declaring a `world activity` importing whatever host interfaces it
    needs — copy an existing sample's `pxc.wit` as a starting point). Only
    accepted when `PXC_ENABLE_ACTIVITY_BUILD=1` — this service then builds it
    server-side via `componentize-py` and installs the result. With the flag
    unset (the default), this path is rejected outright with an explanatory
    error, before any code runs.
- Any files `manifest.assets` declares.

**JS sandboxes are never built server-side**, regardless of the flag.
`componentize-js` needs a bundling step (esbuild/webpack) plus resolving npm
dependencies over the network — a much bigger attack surface to run against
arbitrary uploads than `componentize-py` (which only needs what's already
importable in this process, no network access). Pre-build JS sandboxes
locally and upload the compiled `.wasm`.

**Uploaded Python source can only use what's already installed here** — no
per-upload `pip install`. A `sandbox.py` importing something missing fails
the build with componentize-py's own error message (returned as the HTTP
response body), not a runtime surprise later.

**Safety measures already in place**: `PXC_ENABLE_ACTIVITY_BUILD` off by
default (reject any upload that would need a build, pre-built `.wasm` only),
superuser-only gating on the xblock side, zip-slip / path-traversal
rejection, zip size and entry-count caps, manifest schema validation
*before* any build runs, and a build subprocess timeout (120s). **Not in
place, and worth hardening further if you do enable builds for a large
group of trusted staff**: no per-user rate limiting, no resource limits
(cgroup/memory cap) around the build subprocess beyond the timeout, and the
build runs in this same process/container — consider running libserver
itself in a locked-down container if `PXC_ENABLE_ACTIVITY_BUILD` is on.

## Known limitations / follow-ups

- **`PXC_ACTIVITIES_DIR` must be persistent storage.** Activities installed
  via `/activities/upload` are written there directly — on an ephemeral
  container filesystem they vanish on restart/redeploy. Mount a persistent
  volume, or treat uploads as one-off and bake anything long-lived into the
  image/deployment instead. If you have multiple libserver replicas behind a
  load balancer, they need to share that volume too (uploads aren't
  replicated between instances).
- **Double hop for storage reads.** Every WASM-triggered `storage-*` call and
  every browser download of a storage file goes lib-server → xblock → S3.
  If this becomes a bandwidth/latency problem for large files, the
  alternative (direct S3/boto3 access from this service, bypassing the
  xblock callback) was considered and rejected for the initial cut in favor
  of a single source of truth for storage config — revisit if needed.
