"""Runtime permission levels for activity access.

Local copy of pxc.lib.permission.Permission — pxc-xblock no longer depends on
pxc-lib (moved to the standalone lib-server), so this three-value enum is
duplicated here rather than dragging in wasmtime/pydantic as a dependency
just for it.
"""

from enum import Enum


class Permission(Enum):
    view = "view"
    play = "play"
    edit = "edit"
