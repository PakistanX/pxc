"""URLconf for the PXC internal callback API (see internal_api.py).

Wired into the LMS/CMS urlconf via the plugin app `url_config` in apps.py, at
the `pxc_internal_api` namespace / `^pxc/internal/` prefix.
"""

from django.urls import path

from pxc.xblock import internal_api

app_name = "pxc_xblock"

urlpatterns = [
    path("fields/get", internal_api.fields_get, name="fields_get"),
    path("fields/set", internal_api.fields_set, name="fields_set"),
    path("fields/delete", internal_api.fields_delete, name="fields_delete"),
    path("fields/log/get", internal_api.fields_log_get, name="fields_log_get"),
    path(
        "fields/log/get_after",
        internal_api.fields_log_get_after,
        name="fields_log_get_after",
    ),
    path(
        "fields/log/get_before",
        internal_api.fields_log_get_before,
        name="fields_log_get_before",
    ),
    path("fields/log/append", internal_api.fields_log_append, name="fields_log_append"),
    path("fields/log/delete", internal_api.fields_log_delete, name="fields_log_delete"),
    path(
        "fields/log/delete_before",
        internal_api.fields_log_delete_before,
        name="fields_log_delete_before",
    ),
    path("fields/log/clear", internal_api.fields_log_clear, name="fields_log_clear"),
    path("storage/read", internal_api.storage_read, name="storage_read"),
    path("storage/write", internal_api.storage_write, name="storage_write"),
    path("storage/exists", internal_api.storage_exists, name="storage_exists"),
    path("storage/list", internal_api.storage_list, name="storage_list"),
    path("storage/delete", internal_api.storage_delete, name="storage_delete"),
    path("usernames", internal_api.usernames, name="usernames"),
]
