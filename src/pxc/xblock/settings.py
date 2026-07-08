"""Minimal Django settings for pxc_xblock — used for makemigrations and local testing."""

SECRET_KEY = "dev-only-not-for-production"

INSTALLED_APPS = ["pxc.xblock"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# No-op on Django 2.2 (setting added in 3.2); harmless to leave set for
# forward compatibility if this settings module is ever used against a
# newer Django.
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# Real deployments set these via LMS/CMS env config (e.g. lms.env.yml /
# cms.env.yml "advanced settings", or however your devstack injects Django
# settings) — not here. Defaults below are for local makemigrations/testing
# only, pointed at a lib-server running on the same host.
PXC_LIBSERVER_URL = "http://localhost:9760"
PXC_INTERNAL_SECRET = "dev-insecure-default"
