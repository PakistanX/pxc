"""Tests for PxcXBlock helpers that don't need a full XBlock runtime."""

from pxc.xblock.permission import Permission
from pxc.xblock.permissions import resolve_permission


def test_resolve_permission_anonymous_is_view() -> None:
    assert resolve_permission(user_id=None, user_is_staff=True) == Permission.view


def test_resolve_permission_staff_is_edit() -> None:
    assert resolve_permission(user_id="u1", user_is_staff=True) == Permission.edit


def test_resolve_permission_non_staff_is_play() -> None:
    assert resolve_permission(user_id="u1", user_is_staff=False) == Permission.play
