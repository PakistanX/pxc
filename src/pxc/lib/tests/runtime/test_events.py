from pathlib import Path

import pytest

from pxc.lib.events import EventValidationError
from pxc.lib.runtime import SandboxContext

from .utils import create_manifest, make_activity_runtime


class TestSendEvent:
    """Tests for send_event host function."""

    def test_appends_event_to_pending(self, tmp_path: Path) -> None:
        """Should append event to pending events list with scope and permission."""
        manifest = create_manifest(events={"test.event": {"type": "string"}})
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.send_event("test.event", '"some value"', None, "play")

        events = ctx.clear_pending_events()
        assert len(events) == 1
        assert events[0]["name"] == "test.event"
        assert events[0]["value"] == '"some value"'
        assert events[0]["permission"] == "play"
        context = events[0]["context"]
        assert isinstance(context, dict)
        assert context["activity_id"] == ctx.activity_id
        assert context["course_id"] == ctx.course_id

    def test_appends_multiple_events(self, tmp_path: Path) -> None:
        """Should accumulate multiple events."""
        manifest = create_manifest(
            events={"event1": {"type": "string"}, "event2": {"type": "string"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.send_event("event1", '"value1"', None, "play")
        ctx.send_event("event2", '"value2"', None, "edit")

        events = ctx.clear_pending_events()
        assert len(events) == 2
        assert events[0]["name"] == "event1"
        assert events[0]["permission"] == "play"
        assert events[1]["name"] == "event2"
        assert events[1]["permission"] == "edit"

    def test_allows_declared_fields_change_events(self, tmp_path: Path) -> None:
        """Should allow fields.change.* events when declared in manifest."""
        manifest = create_manifest(events={"fields.change.score": {"type": "integer"}})
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.send_event("fields.change.score", "42", None, "play")

        events = ctx.clear_pending_events()
        assert len(events) == 1
        assert events[0]["name"] == "fields.change.score"
        assert events[0]["value"] == "42"

    def test_raises_for_undeclared_event(self, tmp_path: Path) -> None:
        """Should raise EventValidationError for undeclared event."""
        manifest = create_manifest(events={"declared.event": {"type": "string"}})
        ctx = make_activity_runtime(tmp_path, manifest)

        with pytest.raises(EventValidationError, match="not declared"):
            ctx.send_event("unknown.event", '"value"', None, "play")

    def test_explicit_scope_preserved(self, tmp_path: Path) -> None:
        """Should preserve explicit scope without filling defaults."""
        manifest = create_manifest(events={"test": {"type": "string"}})
        ctx = make_activity_runtime(tmp_path, manifest)

        ctx.send_event(
            "test",
            '"val"',
            SandboxContext({"user-id": "bob", "activity-id": None, "course-id": None}),
            "view",
        )

        events = ctx.clear_pending_events()
        assert events[0]["context"] == {"user_id": "bob"}
        assert events[0]["permission"] == "view"


class TestClearPendingEvents:
    """Tests for clear_pending_events method."""

    def test_returns_and_clears_events(self, tmp_path: Path) -> None:
        """Should return pending events and clear the list."""
        manifest = create_manifest(
            events={"event1": {"type": "string"}, "event2": {"type": "string"}}
        )
        ctx = make_activity_runtime(tmp_path, manifest)
        ctx.send_event("event1", '"value1"', None, "play")
        ctx.send_event("event2", '"value2"', None, "play")

        result = ctx.clear_pending_events()

        assert len(result) == 2
        assert result[0]["name"] == "event1"
        assert result[1]["name"] == "event2"
        assert not ctx.clear_pending_events()

    def test_returns_empty_when_no_events(self, tmp_path: Path) -> None:
        """Should return empty list when no events pending."""
        manifest = create_manifest()
        ctx = make_activity_runtime(tmp_path, manifest)
        assert not ctx.clear_pending_events()
