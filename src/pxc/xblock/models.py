"""Django models for PXC XBlock field and event persistence."""

from django.db import models


class FieldEntry(models.Model):  # type: ignore[misc]
    course_id = models.CharField(max_length=128, db_index=True)
    activity_name = models.CharField(max_length=128, db_index=True)
    activity_id = models.CharField(max_length=128, db_index=True)
    user_id = models.CharField(max_length=64, db_index=True)
    key = models.CharField(max_length=128, db_index=True)
    value = models.JSONField()

    class Meta:
        app_label = "pxc_xblock"
        unique_together = [
            ("course_id", "activity_name", "activity_id", "user_id", "key")
        ]


class FieldLogEntry(models.Model):  # type: ignore[misc]
    """A single entry in a log field. The auto-increment ``id`` is the entry id
    handed back to callers — strictly increasing but possibly sparse across logs.
    """

    course_id = models.CharField(max_length=128, db_index=True)
    activity_name = models.CharField(max_length=128, db_index=True)
    activity_id = models.CharField(max_length=128, db_index=True)
    user_id = models.CharField(max_length=64, db_index=True)
    key = models.CharField(max_length=128, db_index=True)
    value = models.JSONField()

    class Meta:
        app_label = "pxc_xblock"


class PendingEvent(models.Model):  # type: ignore[misc]
    """Persisted events for cross-user delivery via polling."""

    course_id = models.CharField(max_length=128, db_index=True)
    activity_id = models.CharField(max_length=128, db_index=True)
    event_name = models.CharField(max_length=255)
    # event_value is a pre-encoded JSON string emitted by the sandbox; the
    # runtime passes it through opaquely, so we don't decode/re-encode here.
    event_value = models.TextField()
    event_context = models.JSONField()
    event_permission = models.CharField(max_length=16)  # "view" | "play" | "edit"
    # Indexed so the 24h retention sweep in the action handler stays cheap.
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = "pxc_xblock"
        indexes = [models.Index(fields=["course_id", "activity_id", "id"])]
