from django.apps import AppConfig


class PxcXBlockConfig(AppConfig):  # type: ignore[misc]
    name = "pxc.xblock"
    label = "pxc_xblock"

    # Registers internal_urls.py at /pxc/internal/... in both LMS and CMS via
    # edx-platform's plugin app mechanism (openedx.core.djangoapps.plugins) —
    # no manual edx-platform urls.py patch needed. This is the callback API
    # the standalone lib-server uses for field storage, file storage, and
    # username lookups (see internal_api.py).
    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "pxc_xblock",
                "regex": r"^pxc/internal/",
                "relative_path": "internal_urls",
            },
            "cms.djangoapp": {
                "namespace": "pxc_xblock",
                "regex": r"^pxc/internal/",
                "relative_path": "internal_urls",
            },
        },
    }
