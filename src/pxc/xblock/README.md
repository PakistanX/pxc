# PXC XBlock

An XBlock that runs PXC activities natively inside Open edX (LMS and Studio).

## Installation

Add to your Open edX requirements file (e.g. `requirements/edx/private.txt`):

    pxc-xblock @ git+https://github.com/edly-io/pxc.git#subdirectory=src/pxc/xblock

Then register the Django app and run migrations:

```python
# In your Django settings (e.g. lms.env.yml / cms.env.yml advanced settings,
# or a Tutor plugin's settings patch):
INSTALLED_APPS += ["pxc.xblock"]
```

```bash
python manage.py lms migrate pxc_xblock
python manage.py cms migrate pxc_xblock
```

Enable the XBlock in the LMS/CMS advanced settings for your course:

    Advanced Module List → add "pxc"

## How it works

Each XBlock instance holds one `activity_slug` field (content scope) that selects which bundled sample activity to render. Sample activities are shipped inside the wheel under `pxc/xblock/samples/`.

**Studio**: the edit view shows a dropdown of all bundled activities. Selecting one and clicking Save reloads the view with the activity rendered in `edit` permission, so authors can configure it through the activity's own UI.

**LMS**: the student view renders the activity in `play` permission. Actions are sent via HTTP POST to the `action` handler; server-sent events are delivered by polling the `events` handler every 5 seconds.

Field state (learner answers, scores, log entries) is stored in three Django tables (`FieldEntry`, `FieldLogEntry`, `FieldLogSeq`) managed by this app. Cross-user events use a fourth table (`PendingEvent`) as a polling buffer.

## Development

### Regenerating migrations

After changing `models.py`, generate the migration:

```bash
make makemigrations
```

This uses `settings.py` (minimal Django config for local tooling).

## Architecture

See [pxc_xblock.py](./pxc_xblock.py) for the XBlock class, handlers, and permission mapping.
See [models.py](./models.py) for the Django models.
See [field_store.py](./field_store.py) and [file_storage.py](./file_storage.py) for the `pxc-lib` adapter implementations.
