"""FastAPI application for the standalone PXC lib-server.

Hosts `ActivityRuntime` + the wasmtime WASM sandbox (needs Python 3.11+),
decoupled from the LMS/CMS process that embeds `pxc-xblock` (which may run
on an older Python). See pxc.xblock.libserver_client for the caller side.
"""

import hmac
import mimetypes
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel

from pxc.lib.actions import ActionValidationError
from pxc.lib.capabilities import CapabilityError
from pxc.lib.permission import Permission
from pxc.lib.runtime import AssetAccessError, SandboxContext
from pxc.libserver import config
from pxc.libserver.activities import ActivityNotFoundError, get_activity_dir, list_activities
from pxc.libserver.build import BuildError
from pxc.libserver.field_store import HttpFieldStore
from pxc.libserver.file_storage import HttpFileStorage
from pxc.libserver.runtime import ProxyActivityRuntime
from pxc.libserver.upload import UploadError, install_activity_bundle

app = FastAPI(title="PXC Lib Server", version="0.1.0")


def check_internal_secret(
    x_pxc_internal_secret: Annotated[str | None, Header()] = None,
) -> None:
    expected = config.require_secret()
    if not x_pxc_internal_secret or not hmac.compare_digest(
        x_pxc_internal_secret, expected
    ):
        raise HTTPException(status_code=401, detail="Missing or invalid internal secret")


InternalAuth = Depends(check_internal_secret)


class ActivityContext(BaseModel):
    activity_id: str
    course_id: str
    user_id: str
    permission: str
    storage_base_url: str = ""


class ActionRequest(ActivityContext):
    name: str
    value: Any


def _load_runtime(slug: str, ctx: ActivityContext) -> ProxyActivityRuntime:
    try:
        activity_dir = get_activity_dir(slug)
    except ActivityNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        permission = Permission(ctx.permission)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid permission: {e}") from e
    return ProxyActivityRuntime(
        activity_dir=activity_dir,
        field_store=HttpFieldStore(),
        file_storage=HttpFileStorage(ctx.activity_id),
        activity_id=ctx.activity_id,
        course_id=ctx.course_id,
        user_id=ctx.user_id,
        permission=permission,
        storage_base_url=ctx.storage_base_url,
    )


@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/activities", dependencies=[InternalAuth])
def get_activities() -> dict[str, list[str]]:
    return {"activities": list_activities()}


@app.post("/activities/{slug}/state", dependencies=[InternalAuth])
def get_state(slug: str, ctx: ActivityContext) -> dict[str, Any]:
    runtime = _load_runtime(slug, ctx)
    return runtime.get_state()


@app.post("/activities/{slug}/action", dependencies=[InternalAuth])
def post_action(slug: str, req: ActionRequest) -> dict[str, Any]:
    runtime = _load_runtime(slug, req)
    try:
        runtime.on_action(req.name, req.value)
    except ActionValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    events = runtime.clear_pending_events()
    grades = runtime.clear_pending_grades()
    return {"events": events, "grades": grades}


@app.get("/activities/{slug}/ui", dependencies=[InternalAuth])
def get_ui(
    slug: str,
    activity_id: str = "",
    course_id: str = "",
    user_id: str = "",
) -> Response:
    runtime = _load_runtime(
        slug,
        ActivityContext(
            activity_id=activity_id,
            course_id=course_id,
            user_id=user_id,
            permission=Permission.view.value,
        ),
    )
    try:
        ui_path = runtime.get_ui_path()
    except AssetAccessError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return Response(ui_path.read_bytes(), media_type="application/javascript")


@app.get("/activities/{slug}/asset/{path:path}", dependencies=[InternalAuth])
def get_asset(
    slug: str,
    path: str,
    activity_id: str = "",
    course_id: str = "",
    user_id: str = "",
) -> Response:
    runtime = _load_runtime(
        slug,
        ActivityContext(
            activity_id=activity_id,
            course_id=course_id,
            user_id=user_id,
            permission=Permission.view.value,
        ),
    )
    try:
        asset_path = runtime.get_asset_path(path)
    except AssetAccessError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    content_type, _ = mimetypes.guess_type(str(asset_path))
    return Response(
        asset_path.read_bytes(), media_type=content_type or "application/octet-stream"
    )


class StorageReadRequest(ActivityContext):
    name: str
    path: str
    context_override: SandboxContext | None = None


@app.post("/activities/{slug}/storage/read", dependencies=[InternalAuth])
def storage_read(slug: str, req: StorageReadRequest) -> Response:
    runtime = _load_runtime(slug, req)
    try:
        content = runtime.storage_read(req.name, req.path, req.context_override)
    except (CapabilityError, AssetAccessError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    content_type, _ = mimetypes.guess_type(req.path)
    return Response(content, media_type=content_type or "application/octet-stream")


@app.post("/activities/upload", dependencies=[InternalAuth])
async def upload_activity(bundle: UploadFile) -> dict[str, str]:
    """Install a course-staff-uploaded activity bundle (zip).

    Not reachable from a browser directly — only via pxc-xblock's
    Studio-only `upload_activity` handler, which is itself gated on author
    (edit) permission. See pxc.libserver.upload for the bundle format and
    pxc.libserver.build for the (Python-source-only) server-side build.
    """
    zip_bytes = await bundle.read()
    try:
        slug = install_activity_bundle(zip_bytes)
    except UploadError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except BuildError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"slug": slug}
