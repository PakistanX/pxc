# PXC XBlock

An XBlock that runs PXC activities natively inside Open edX (LMS and Studio).

## Architecture: split from pxc-lib

This package used to import `pxc-lib` directly and run the WASM sandbox
(wasmtime) in-process. It now talks over HTTP to a separately-deployed
**[pxc-libserver](../libserver/README.md)**, so this package has no
`wasmtime`/`pydantic>=2`/`jsonschema` dependency and can run on an older
Python than the sandbox execution requires. See
[libserver_client.py](./libserver_client.py) for the HTTP client and
[internal_api.py](./internal_api.py) for the callback API the lib-server
uses to reach back into this app's field storage / file storage / user
lookups.

**You must deploy `pxc-libserver` separately** — it's a standalone process
(not a Tutor plugin, not embedded in the LMS/CMS process). See its README for
running instructions.

### Compatibility — Python 3.5 / Django 2.2

This package's own code is written to run on **Python 3.5 and Django 2.2**
(Juniper-era Open edX): no f-strings, no PEP 526 variable annotations, no
bare generic subscripting (`dict[str, int]`), no `X | Y` unions, no
`from __future__ import annotations` (that itself needs 3.7+), no
`importlib.resources.files` (3.9+ — package resources are read via a plain
`__file__`-relative path instead), and no `django.db.models.JSONField`
(Django 3.1+ — `FieldEntry`/`FieldLogEntry`/`PendingEvent` use `TextField`
with manual `json.dumps`/`json.loads` instead, see models.py). HTTP calls to
pxc-libserver use `requests`, not `httpx` (current httpx needs Python 3.8+).

**Packaging**: there is deliberately no `pyproject.toml` `[project]` table
here — only `setup.py`. A real Python 3.5 interpreter resolves setuptools
~28.x, which predates both PEP 621 (`[project]` metadata, needs setuptools
61+) and PEP 660 (proper editable-wheel installs, needs setuptools 64+). A
plain `setup.py` is the only layout that both an ancient and a modern
toolchain can install without special-casing. One consequence: **`pip
install -e .` silently produces a broken install on any Python version** —
it doesn't error, but it's actively dangerous (shadows Python's own
`models` name platform-wide). Always use a regular (non-editable) `pip
install .` / `pip install <git-url>` instead — see "Installation" below for
the full explanation and the live-editing alternative.

This was verified for real, not just syntax-checked: the full test suite
plus request-level smoke tests (models, `DjangoFieldStore`,
`DjangoFileStorage`, every `internal_api.py` view via Django's
`RequestFactory`, `libserver_client.py`'s HTTP logic against fake responses)
ran green on an actual Python 3.5.10 interpreter with Django 2.2.28. A
non-editable `pip install .` of this package was also verified end-to-end
on that interpreter (correct `site-packages/pxc/xblock/...` layout, XBlock
entry point registered, `PxcXBlock` importable).

**What that verification could *not* clear — check this yourself**: the
`xblock` and `web-fragments` packages currently on PyPI already contain
f-strings even in releases from Juniper's own release window (e.g. `XBlock`
1.5.1, uploaded 2021-09-01) — genuine Python 3.5 cannot import *any*
`xblock`/`web-fragments` version installable fresh from PyPI today. Your
platform must already have older, compatible pins of these two packages
(edx-platform's own frozen requirements) — don't let pip resolve "latest"
for them, and don't add version constraints for them here without checking
what your platform actually has installed. Same goes for `Django`: pin it to
match your edx-platform checkout exactly, not a second/newer copy.

## Installation

**Never install this package with `pip install -e .` / editable mode, on
any Python version.** This package's `setup.py` maps `pxc.xblock` onto the
`xblock/` source directory directly (`package_dir={"pxc.xblock": "."}`) so
the physical repo layout doesn't need a redundant `pxc/xblock/` nesting.
Non-editable installs handle that fine (files get copied into the correct
`site-packages/pxc/xblock/...` layout at install time). Editable installs
(`pip install -e .` / `python setup.py develop`) instead add the raw
`xblock/` directory itself to `sys.path` verbatim — since that directory has
no `pxc/` parent on disk, every top-level file in it (`models.py`,
`field_store.py`, ...) becomes importable as a **bare top-level module**,
shadowing anything else in the process with the same name. In practice this
manifests as `ImportError: No module named 'models.settings'; 'models' is
not a package` from edx-platform's own `cms/djangoapps/contentstore` code
(it does `from models.settings.course_grading import CourseGradingModel`),
or Django's app registry raising `Application labels aren't unique`. If
you've already installed it editable, undo it:

```bash
pip uninstall pxc-xblock -y
# adjust to your actual site-packages path:
rm -f <venv>/lib/python*/site-packages/easy-install.pth
rm -f <venv>/lib/python*/site-packages/pxc-xblock.egg-link
pip install /path/to/src/pxc/xblock
```

(Check `easy-install.pth`'s contents before deleting outright if other
packages might share it — only the line pointing at `.../pxc/xblock` is the
problem.) For live development iteration without reinstalling on every
change, set `PYTHONPATH` to this repo's `src/` directory (the parent of
`pxc/`, not `xblock/` itself) instead of using any install trickery —
`src/pxc` has no `__init__.py` (implicit namespace package), so
`import pxc.xblock.models` resolves correctly to `src/pxc/xblock/models.py`
without exposing anything as a bare top-level module.

Add to your Open edX requirements file (e.g. `requirements/edx/private.txt`):

    pxc-xblock @ git+https://github.com/edly-io/pxc.git#subdirectory=src/pxc/xblock

Then configure and run migrations:

```python
# In your Django settings (e.g. lms/envs/private.py / cms/envs/private.py,
# or however your devstack injects Django settings):
#
# Do NOT add "pxc.xblock" to INSTALLED_APPS manually — its setup.py declares
# lms.djangoapp/cms.djangoapp entry points, so edx-platform's plugin-app
# loader (openedx.core.djangoapps.plugins) discovers and installs it itself.
# Adding it by hand as well double-registers the app and Django raises
# "Application labels aren't unique, duplicates: pxc_xblock" at startup.

# Where the standalone pxc-libserver is reachable, and the secret shared with
# it (see pxc.libserver.config on the other side — must match exactly):
PXC_LIBSERVER_URL = "http://<host running pxc-libserver>:9760"
PXC_INTERNAL_SECRET = "<a real secret, not the dev default>"
```

```bash
python manage.py lms migrate pxc_xblock
python manage.py cms migrate pxc_xblock
```

Sanity check the plugin actually registered before moving on:

```bash
python manage.py lms shell -c "from django.urls import reverse; print(reverse('pxc_xblock:fields_get'))"
python manage.py cms shell -c "from django.urls import reverse; print(reverse('pxc_xblock:fields_get'))"
```
Both should print `/pxc/internal/fields/get`. If either raises `NoReverseMatch`, the package was installed before the entry points existed in `setup.py` — reinstall with `pip install . --force-reinstall --no-deps` (entry points are baked into installed metadata at install time, editing the source file alone doesn't update it) and restart that service.

Enable the XBlock in the LMS/CMS advanced settings for your course:

    Advanced Module List → add "pxc"

The `/pxc/internal/...` callback API (internal_urls.py) registers itself
automatically in both LMS and CMS via edx-platform's Django plugin-app
mechanism (`PxcXBlockConfig.plugin_app` in [apps.py](./apps.py)) — no manual
urls.py patch needed. It is **not** meant to be reachable from a browser;
make sure your ingress/proxy doesn't expose it beyond the private network
pxc-libserver runs on.

## How it works

Each XBlock instance holds one `activity_slug` field (content scope) that selects which activity to render. Activity content (manifest.json/sandbox.wasm/ui.js/assets) is no longer shipped in this wheel — it's read by `pxc-libserver` from its own `PXC_ACTIVITIES_DIR`; this app only knows the slug and asks the lib-server for state/actions/assets over HTTP. The `samples/` symlink here is a devstack-local convenience (`pxc-libserver`'s default config points at it), not something this package reads at runtime.

**Studio**: the edit view shows a dropdown of all bundled activities, a
"Scored" checkbox, a "Problem Weight" field, an "Upload new activity"
widget that proxies to pxc-libserver's `/activities/upload` (see its README
for the bundle format and the `PXC_ENABLE_ACTIVITY_BUILD` flag gating
server-side `componentize-py` builds), and a "Reset a learner's attempt"
widget (see "Resetting a learner" below). Selecting an activity and clicking
Save reloads the view with the activity rendered in `edit` permission, so
authors can configure it through the activity's own UI.

**Upload is superuser-only, but the widget is always visible** — this is
deliberate, not a bug. `studio_view()`'s render path carries no reliable
user identity in every environment we've tested (confirmed by a diagnostic:
`scope_ids.user_id` was `None` there, and even `self.runtime.service(self,
"user")` raised) — Studio's block-settings render and Studio's *handler
calls* (`action`/`save_settings`/`upload_activity`) go through genuinely
different code paths, and only the latter reliably carries the real
authenticated user. So the widget can't be proactively hidden based on
`is_superuser` at render time; instead, `upload_activity` (a live
authenticated request, same as `save_settings`) enforces it strictly
server-side via a direct Django `User.is_superuser` lookup — deliberately
not the same "course author" permission used for everything else on this
page, since uploading runs arbitrary Python source through a compiler, a
platform-wide risk, not a per-course one. Non-superusers who click Upload
get a clean 403 with an explanatory message; nothing runs.

**`PXC_ENABLE_ACTIVITY_BUILD`** (set on pxc-libserver, not here) is a
separate, independent gate: it only affects uploads that need
`componentize-py` to build a `sandbox.py`. Uploading a zip with an
already-built `sandbox.wasm` inside works **regardless of this flag** — no
code runs server-side for that path either way. Leave it unset unless you
specifically need staff to upload raw Python sandbox source.

**LMS**: the student view renders the activity in `play` permission. Actions are sent via HTTP POST to the `action` handler; server-sent events are delivered by polling the `events` handler every 5 seconds.

Field state (learner answers, scores, log entries) is stored in three Django tables (`FieldEntry`, `FieldLogEntry`, `FieldLogSeq`) managed by this app. Cross-user events use a fourth table (`PendingEvent`) as a polling buffer.

**Grading & completion**: activities calling `reportScored`/`reportPassed`/
`reportFailed`/`reportCompleted`/`reportProgressed` end up in the `action`
handler's `result["grades"]` list (see `pxc.lib.runtime.GradeEvent`), which
`_publish_grade_event` records **directly against edx-platform's own
primitives** — `lms.djangoapps.grades.signals.signals.SCORE_PUBLISHED.send(...)`
for `"grade"` events, `completion.models.BlockCompletion.objects.
submit_completion(...)` for `"completion"` events — rather than going through
`self.runtime.publish(self, event_type, payload)`. That's a deliberate
departure from the "normal" XBlock way of doing this: `publish()` alone (even
with `CompletableXBlockMixin` correctly mixed in, see below) did not reliably
reach the completion app's receiver in the environment this was built
against — confirmed by repeated testing, checkmark stayed unmarked. Calling
the underlying signal/API directly is the same thing the platform's own
`publish_user_score`-style offline grade-fix tooling does, and is what's
actually verified working here.

Grading is gated on the **`has_score` field** (default on, editable
per-instance from Studio, not a hardcoded class attribute) plus the `weight`
field — set at the *sandbox* level (don't call `reportScored`/etc. if you
don't want a grade published) rather than in `_publish_grade_event` itself,
which doesn't re-check `has_score`. The activity must also be placed in a
graded subsection like any other scored component. Turn `has_score` off for
activities that only track completion.

`PxcXBlock` still mixes in `xblock.completable.CompletableXBlockMixin` (sets
`has_custom_completion = True` / `completion_mode = COMPLETABLE`) — this no
longer matters for whether `_publish_grade_event`'s direct
`BlockCompletion.submit_completion` call works (it doesn't go through the
mixin/publish path at all), but it's still the correct declaration so the
platform's own default view-based completion inference doesn't fight with
what this block reports. If completion still doesn't update after all this,
check that `ENABLE_COMPLETION_TRACKING` (or your release's equivalent feature
flag) is on and that the `completion` Django app is installed + migrated.
`_publish_grade_event` imports `completion`/`lms.djangoapps.grades` lazily
and logs (not raises) on `ImportError`, so a misconfigured install doesn't
turn a learner's submit into a 500 — check the LMS/CMS logs for "Could not
import" if grades/completion silently don't land.

**Per-user events must target the calling user, not broadcast.** Every
learner viewing the same unit shares one `activity_id` (the block's
usage id) and polls the same `events` handler — a sandbox `sendEvent(name,
value, context, permission)` call with `context=null` delivers to *every*
viewer at that permission level, not just the caller. For per-student data
(the learner's own prompt/answer/grade/etc.), always pass
`{ userId: context.userId }` instead of `null` — see
`samples/m1l8-email-prompt-craft/sandbox.js` or `samples/essay/sandbox.js` for
the pattern. Reserve `null` for genuinely shared/course-scoped data (e.g.
`credentials.status`, since the underlying field itself is course-scoped).
Getting this wrong doesn't error — it silently leaks one learner's activity
state into every classmate's open tab.

**Resetting a learner**: the Studio edit view's "Reset a learner's attempt"
widget (backed by the `reset_learner` handler) takes a student email and
deletes every `FieldEntry`/`FieldLogEntry` row *this specific block instance*
wrote for that user (scenario/prompt/output/attempts/grade/submitted/etc.) —
see `field_store.reset_learner`. It does **not** touch course/activity/
global-scoped fields (e.g. a shared API key), and it does **not** undo the
LMS's own grade/completion record for that student (that's Open edX's
`StudentModule`/grades tables, set by the `publish()` calls above) — use the
platform's own "Reset Student Attempts" / grade override tooling for that
too, in addition to this, if the activity is scored.

## Development

### Regenerating migrations

After changing `models.py`, generate the migration:

```bash
make makemigrations
```

This uses `settings.py` (minimal Django config for local tooling).

## Architecture

See [pxc_xblock.py](./pxc_xblock.py) for the XBlock class, handlers, and permission mapping.
See [libserver_client.py](./libserver_client.py) for the HTTP client to pxc-libserver.
See [internal_api.py](./internal_api.py) / [internal_urls.py](./internal_urls.py) for the callback API pxc-libserver uses.
See [models.py](./models.py) for the Django models.
See [field_store.py](./field_store.py) and [file_storage.py](./file_storage.py) for the field/file persistence implementations (called from internal_api.py, not injected into an in-process runtime anymore).
