"""Minimal Django settings for pxc_xblock — used for makemigrations and local testing."""

INSTALLED_APPS: list[str] = ["pxc.xblock"]

DATABASES: dict[str, dict[str, str]] = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

DEFAULT_AUTO_FIELD: str = "django.db.models.AutoField"
