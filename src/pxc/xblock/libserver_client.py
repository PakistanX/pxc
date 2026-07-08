"""HTTP client for the standalone PXC lib-server.

Replaces the in-process `pxc.lib.runtime.ActivityRuntime` this xblock used to
instantiate directly. The lib-server owns manifest parsing, capability/action/
event validation, and wasmtime sandbox execution (all of which need a newer
Python than this LMS/CMS install) — this client only speaks HTTP to it.

Uses ``requests`` rather than ``httpx``: this package targets Python 3.5
(Juniper-era Open edX), and current httpx releases require Python 3.8+.
"""

import mimetypes
from typing import Any, Dict, List, Optional, Tuple

import requests
from django.conf import settings

from pxc.xblock.permission import Permission


class LibServerError(Exception):
    """Raised on any unexpected (5xx) response from the lib-server."""


class ActivityNotFoundError(Exception):
    """Raised when the requested activity slug has no bundle on the lib-server."""


class ActionValidationError(Exception):
    """Raised when the lib-server rejects an action (undeclared / bad payload / view-mode)."""


class UploadValidationError(Exception):
    """Raised when an uploaded activity bundle is malformed (bad zip/manifest/slug)."""


class BuildFailedError(Exception):
    """Raised when componentize-py failed to build an uploaded Python sandbox.

    ``str(e)`` is the compiler output — safe to show to the uploading course
    staff member (it's their own build's errors)."""


def _base_url():
    # type: () -> str
    url = getattr(settings, "PXC_LIBSERVER_URL", "http://localhost:9760")
    return url.rstrip("/")


def _secret():
    # type: () -> str
    secret = getattr(settings, "PXC_INTERNAL_SECRET", "")
    if not secret:
        raise LibServerError(
            "PXC_INTERNAL_SECRET is not configured; refusing to call the lib-server "
            "without an authenticated channel."
        )
    return secret


def _timeout():
    # type: () -> float
    return getattr(settings, "PXC_LIBSERVER_TIMEOUT", 10.0)


def _get(path, params=None):
    # type: (str, Optional[Dict[str, str]]) -> requests.Response
    return requests.get(
        _base_url() + path,
        params=params,
        headers={"X-PXC-Internal-Secret": _secret()},
        timeout=_timeout(),
    )


def _post(path, json_body):
    # type: (str, Dict[str, Any]) -> requests.Response
    return requests.post(
        _base_url() + path,
        json=json_body,
        headers={"X-PXC-Internal-Secret": _secret()},
        timeout=_timeout(),
    )


def _raise_for_status(resp):
    # type: (requests.Response) -> None
    if resp.status_code == 404:
        raise ActivityNotFoundError(resp.text)
    if resp.status_code == 400:
        raise ActionValidationError(resp.json().get("detail", resp.text))
    if resp.status_code >= 400:
        raise LibServerError("{0}: {1}".format(resp.status_code, resp.text[:500]))


def list_activities():
    # type: () -> List[str]
    resp = _get("/activities")
    _raise_for_status(resp)
    return resp.json()["activities"]


def get_state(slug, activity_id, course_id, user_id, permission, storage_base_url):
    # type: (str, str, str, str, Permission, str) -> Dict[str, Any]
    resp = _post(
        "/activities/{0}/state".format(slug),
        {
            "activity_id": activity_id,
            "course_id": course_id,
            "user_id": user_id,
            "permission": permission.value,
            "storage_base_url": storage_base_url,
        },
    )
    _raise_for_status(resp)
    return resp.json()


def on_action(
    slug,
    activity_id,
    course_id,
    user_id,
    permission,
    storage_base_url,
    name,
    value,
):
    # type: (str, str, str, str, Permission, str, str, Any) -> Dict[str, List[Dict[str, Any]]]
    """Returns ``{"events": [...], "grades": [...]}``.

    ``grades`` entries are ``{"event_type": "grade"|"completion", "payload": {...}}``
    — see pxc.lib.runtime.GradeEvent. Caller (pxc_xblock.py) is responsible
    for actually publishing them via ``self.runtime.publish(...)``; this
    process has no XBlock runtime context of its own.
    """
    resp = _post(
        "/activities/{0}/action".format(slug),
        {
            "activity_id": activity_id,
            "course_id": course_id,
            "user_id": user_id,
            "permission": permission.value,
            "storage_base_url": storage_base_url,
            "name": name,
            "value": value,
        },
    )
    _raise_for_status(resp)
    body = resp.json()
    return {"events": body["events"], "grades": body.get("grades", [])}


def _guess_content_type(path, resp):
    # type: (str, requests.Response) -> str
    guessed, _ = mimetypes.guess_type(path)
    return guessed or resp.headers.get("content-type", "application/octet-stream")


def get_ui(slug, activity_id, course_id, user_id):
    # type: (str, str, str, str) -> Tuple[bytes, str]
    resp = _get(
        "/activities/{0}/ui".format(slug),
        params={"activity_id": activity_id, "course_id": course_id, "user_id": user_id},
    )
    _raise_for_status(resp)
    return resp.content, "application/javascript"


def get_asset(slug, path, activity_id, course_id, user_id):
    # type: (str, str, str, str, str) -> Tuple[bytes, str]
    resp = _get(
        "/activities/{0}/asset/{1}".format(slug, path),
        params={"activity_id": activity_id, "course_id": course_id, "user_id": user_id},
    )
    _raise_for_status(resp)
    return resp.content, _guess_content_type(path, resp)


def storage_read(
    slug, activity_id, course_id, user_id, name, path, context_override=None
):
    # type: (str, str, str, str, str, str, Optional[Dict[str, Optional[str]]]) -> Tuple[bytes, str]
    resp = _post(
        "/activities/{0}/storage/read".format(slug),
        {
            "activity_id": activity_id,
            "course_id": course_id,
            "user_id": user_id,
            "permission": Permission.view.value,
            "name": name,
            "path": path,
            "context_override": context_override,
        },
    )
    _raise_for_status(resp)
    return resp.content, _guess_content_type(path, resp)


def upload_activity(zip_bytes, filename):
    # type: (bytes, str) -> str
    """Upload an activity bundle (zip) for validation/build/install.

    Returns the installed activity's slug.

    Raises:
        UploadValidationError: Bad zip/manifest/slug (400).
        BuildFailedError: componentize-py failed on an uploaded Python
            sandbox source (422).
        LibServerError: Anything else unexpected.
    """
    resp = requests.post(
        _base_url() + "/activities/upload",
        files={"bundle": (filename, zip_bytes, "application/zip")},
        headers={"X-PXC-Internal-Secret": _secret()},
        timeout=_timeout(),
    )
    if resp.status_code == 400:
        raise UploadValidationError(resp.json().get("detail", resp.text))
    if resp.status_code == 422:
        raise BuildFailedError(resp.json().get("detail", resp.text))
    if resp.status_code >= 400:
        raise LibServerError("{0}: {1}".format(resp.status_code, resp.text[:500]))
    return resp.json()["slug"]
