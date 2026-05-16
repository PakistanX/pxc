import logging
import mimetypes
from typing import NamedTuple

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlmodel import Session

from pxc.lib.actions import ActionValidationError
from pxc.lib.capabilities import CapabilityError
from pxc.lib.event_bus import EventBus
from pxc.lib.file_storage import FileStorageError
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime, AssetAccessError, SandboxContext
from pxc.lib.signing import TokenError, verify_token
from pxc.notebook import constants
from pxc.notebook.auth import (
    SESSION_COOKIE,
    get_current_user,
    lookup_user,
    lookup_user_by_api_token,
)
from pxc.notebook.db import get_session
from pxc.notebook.models import CourseActivity, PageActivity, User
from pxc.notebook.views.activities import load_activity
from pxc.notebook.views.course_activities import load_course_activity

logger = logging.getLogger(__name__)

router = APIRouter()

event_bus = EventBus()

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "null",
    "Vary": "Origin",
    "Cross-Origin-Resource-Policy": "cross-origin",
}

_IFRAME_JS_PATH = constants.STATIC_DIR / "js" / "pxc-iframe.js"


class ActivityAction(BaseModel):
    name: str
    value: object


class ActivityInfo(NamedTuple):
    id: str
    activity_type: str
    course_id: str
    is_course_activity: bool
    is_owner: bool


def resolve_activity(session: Session, activity_id: str, user: User) -> ActivityInfo:
    """Look up an activity in both PageActivity and CourseActivity tables.

    Any authenticated user can resolve any activity; non-owners are restricted
    to play permission by `effective_permission()`.
    """
    pa = session.get(PageActivity, activity_id)
    if pa:
        course = pa.page.course
        return ActivityInfo(
            pa.id, pa.activity_type, course.id, False, course.owner_id == user.id
        )
    ca = session.get(CourseActivity, activity_id)
    if ca:
        return ActivityInfo(
            ca.id,
            ca.activity_type,
            ca.course_id,
            True,
            ca.course.owner_id == user.id,
        )
    raise HTTPException(status_code=404, detail="Activity not found")


def check_permission(info: ActivityInfo, permission: Permission) -> None:
    """Non-owners may only request play permission."""
    if not info.is_owner and permission != Permission.play:
        raise HTTPException(status_code=403, detail="Forbidden")


def load_any_activity(
    info: ActivityInfo, user_id: str, permission: Permission
) -> ActivityRuntime:
    """Load the runtime for either a page or course activity."""
    if info.is_course_activity:
        return load_course_activity(
            info.activity_type, info.id, info.course_id, user_id, permission
        )
    return load_activity(
        info.activity_type, info.id, info.course_id, user_id, permission
    )


def _load_from_pxc_token(
    token: str, activity_id: str, session: Session
) -> ActivityRuntime:
    """Verify HMAC token and load activity runtime (no session cookie required)."""
    try:
        claims = verify_token(token)
    except TokenError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e
    if str(claims["aid"]) != activity_id:
        raise HTTPException(status_code=403, detail="Token mismatch")

    user_id = str(claims["uid"])
    course_id = str(claims["cid"])
    permission = Permission(str(claims["p"]))

    pa = session.get(PageActivity, activity_id)
    if pa:
        return load_activity(
            pa.activity_type, activity_id, course_id, user_id, permission
        )
    ca = session.get(CourseActivity, activity_id)
    if ca:
        return load_course_activity(
            ca.activity_type, activity_id, course_id, user_id, permission
        )
    raise HTTPException(status_code=404, detail="Activity not found")


def _require_user(request: Request, session: Session) -> User:
    """Authenticate from session cookie or Bearer token; raise 401 if missing."""
    token = request.cookies.get(SESSION_COOKIE)
    user = lookup_user(session, token)
    if not user:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            user = lookup_user_by_api_token(session, auth[7:])
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


@router.get("/_pxc/iframe", include_in_schema=False)
async def pxc_iframe_page() -> Response:
    """Bootstrap HTML document loaded inside sandboxed activity iframes."""
    return Response(
        content=(
            '<!DOCTYPE html><html><head><meta charset="UTF-8">'
            "<style>body{margin:0}</style></head>"
            '<body><div id="root"></div>'
            '<script type="module" src="/_pxc/iframe.js"></script>'
            "</body></html>"
        ),
        media_type="text/html",
    )


@router.get("/_pxc/iframe.js", include_in_schema=False)
async def pxc_iframe_js() -> FileResponse:
    """pxc-iframe.js served with CORS so null-origin iframes can load it."""
    return FileResponse(
        _IFRAME_JS_PATH,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cross-Origin-Resource-Policy": "cross-origin",
        },
    )


@router.get(
    "/a/{activity_id}/ui.js",
    summary="Serve the activity UI script",
)
async def activity_ui(
    activity_id: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> FileResponse:
    user = _require_user(request, session)
    info = resolve_activity(session, activity_id, user)
    ctx = load_any_activity(info, user.id, Permission.play)
    try:
        full_path = ctx.get_ui_path()
    except AssetAccessError as e:
        raise HTTPException(status_code=404, detail="Access denied") from e
    return FileResponse(full_path)


@router.get(
    "/a/{activity_id}/{file_path:path}",
    summary="Serve an activity static asset",
)
async def activity_asset(
    activity_id: str,
    file_path: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
) -> FileResponse:
    user = _require_user(request, session)
    info = resolve_activity(session, activity_id, user)
    ctx = load_any_activity(info, user.id, Permission.play)
    try:
        full_path = ctx.get_asset_path(file_path)
    except AssetAccessError as e:
        raise HTTPException(status_code=404, detail="Access denied") from e
    return FileResponse(full_path)


@router.get(
    "/activity/{activity_id}/storage/{storage_name}/{file_path:path}",
    summary="Serve a file from activity storage",
)
async def storage_file(
    activity_id: str,
    storage_name: str,
    file_path: str,
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    activity_id_override: str | None = Query(None, alias="activity_id"),
    course_id_override: str | None = Query(None, alias="course_id"),
    user_id_override: str | None = Query(None, alias="user_id"),
) -> Response:
    user = _require_user(request, session)
    info = resolve_activity(session, activity_id, user)
    ctx = load_any_activity(info, user.id, Permission.play)
    context: SandboxContext | None = None
    if activity_id_override or course_id_override or user_id_override:
        context = {
            "activity-id": activity_id_override,
            "course-id": course_id_override,
            "user-id": user_id_override,
        }
    try:
        content = ctx.storage_read(storage_name, file_path, context)
    except CapabilityError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileStorageError as e:
        raise HTTPException(status_code=404, detail="File not found") from e
    media_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)


@router.get(
    "/_pxc/t/{token}/a/{activity_id}/ui.js",
    summary="Serve the activity UI script (token-in-path auth for sandboxed iframes)",
)
async def activity_ui_token(
    token: str,
    activity_id: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    ctx = _load_from_pxc_token(token, activity_id, session)
    try:
        full_path = ctx.get_ui_path()
    except AssetAccessError as e:
        raise HTTPException(status_code=404, detail="Access denied") from e
    return FileResponse(full_path, headers=_CORS_HEADERS)


@router.get(
    "/_pxc/t/{token}/a/{activity_id}/{file_path:path}",
    summary="Serve an activity static asset (token-in-path auth for sandboxed iframes)",
)
async def activity_asset_token(
    token: str,
    activity_id: str,
    file_path: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    ctx = _load_from_pxc_token(token, activity_id, session)
    try:
        full_path = ctx.get_asset_path(file_path)
    except AssetAccessError as e:
        raise HTTPException(status_code=404, detail="Access denied") from e
    return FileResponse(full_path, headers=_CORS_HEADERS)


@router.get(
    "/_pxc/t/{token}/activity/{activity_id}/storage/{storage_name}/{file_path:path}",
    summary="Serve a storage file (token-in-path auth for sandboxed iframes)",
)
async def storage_file_token(
    token: str,
    activity_id: str,
    storage_name: str,
    file_path: str,
    session: Session = Depends(get_session),
) -> Response:
    ctx = _load_from_pxc_token(token, activity_id, session)
    try:
        content = ctx.storage_read(storage_name, file_path, None)
    except CapabilityError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except FileStorageError as e:
        raise HTTPException(status_code=404, detail="File not found") from e
    media_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type, headers=_CORS_HEADERS)


@router.post(
    "/api/activity/{activity_id}/{permission}/actions",
    summary="Trigger an action",
)
async def activity_actions(
    activity_id: str,
    permission: Permission,
    action: ActivityAction,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> None:
    """Trigger an activity action."""
    info = resolve_activity(session, activity_id, current_user)
    check_permission(info, permission)

    ctx = load_any_activity(info, current_user.id, permission)
    try:
        ctx.on_action(action.name, action.value)
    except ActionValidationError as e:
        raise HTTPException(status_code=400, detail=f"Invalid action: {e}") from e

    events = ctx.clear_pending_events()
    await event_bus.publish(info.activity_type, events)


@router.websocket("/api/activity/{activity_id}/{permission}/ws")
async def activity_ws(
    websocket: WebSocket,
    activity_id: str,
    permission: Permission,
    session: Session = Depends(get_session),
) -> None:
    policy_violation_code = 1008

    token = websocket.cookies.get(SESSION_COOKIE)
    current_user = lookup_user(session, token)
    if not current_user:
        await websocket.close(code=policy_violation_code)
        return

    try:
        info = resolve_activity(session, activity_id, current_user)
        check_permission(info, permission)
    except HTTPException:
        await websocket.close(code=policy_violation_code)
        return
    await websocket.accept()

    subscriber = event_bus.subscribe(
        info.activity_type,
        websocket,
        current_user.id,
        permission,
        info.course_id,
        activity_id,
    )

    while True:
        try:
            data = await websocket.receive_json()
        except WebSocketDisconnect:
            event_bus.unsubscribe(info.activity_type, subscriber)
            return
        try:
            action_name = data["action"]
            action_value = data["value"]
        except KeyError:
            # TODO raise error?
            continue

        ctx = load_any_activity(info, current_user.id, permission)
        try:
            ctx.on_action(action_name, action_value)
        except ActionValidationError as e:
            # TODO should we return an error to the frontend?
            logger.warning("WS action validation error: %s", e)
            continue

        events = ctx.clear_pending_events()
        await event_bus.publish(info.activity_type, events)
