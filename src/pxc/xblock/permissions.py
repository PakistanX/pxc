"""Permission resolution from XBlock runtime context.

Kept separate from ``pxc_xblock`` so it can be unit-tested without importing
the XBlock SDK (whose namespace collides with the local ``pxc.xblock`` package
under pytest's default rootdir discovery).
"""

from typing import Any

from pxc.xblock.permission import Permission


def resolve_permission(user_id: Any, user_is_staff: bool) -> Permission:
    """Map an XBlock caller's identity to a PXC Permission.

    The client-supplied permission value is intentionally ignored: trusting it
    would let a student request edit-mode execution and edit-scoped event
    delivery.
    """
    if user_id is None:
        return Permission.view
    if user_is_staff:
        return Permission.edit
    return Permission.play
