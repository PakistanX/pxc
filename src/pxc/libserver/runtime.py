from pathlib import Path

from pxc.lib.field_store import FieldStore
from pxc.lib.file_storage import FileStorage
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime, SandboxContext
from pxc.libserver import client


class ProxyActivityRuntime(ActivityRuntime):
    """ActivityRuntime for the standalone libserver.

    Field/storage/username host functions are backed by HTTP-callback
    adapters (see field_store.py, file_storage.py) that reach back into
    pxc-xblock's internal API — this process never touches the LMS database
    or S3 credentials directly. ``storage_url`` still needs to resolve to a
    browser-reachable URL, which is the xblock's own `storage` handler, so
    the caller must pass the same handler URL the xblock would have built
    for ``XBlockActivityRuntime`` (see pxc.xblock.pxc_xblock._make_runtime,
    now threaded through the /state and /action request payloads instead).
    """

    def __init__(
        self,
        activity_dir: Path,
        field_store: FieldStore,
        file_storage: FileStorage,
        activity_id: str,
        course_id: str,
        user_id: str,
        permission: Permission,
        *,
        storage_base_url: str = "",
    ) -> None:
        super().__init__(
            activity_dir,
            field_store,
            file_storage,
            activity_id,
            course_id,
            user_id,
            permission,
        )
        self._storage_base_url = storage_base_url

    def storage_url(
        self, name: str, path: str, context: SandboxContext | None = None
    ) -> str:
        base = super().storage_url(name, path, context)
        prefix = f"/activity/{self._activity_id}/storage"
        return f"{self._storage_base_url}{base[len(prefix):]}"

    def get_usernames(self, ids: list[str]) -> list[tuple[str, str]]:
        result = client.post("/usernames", {"ids": ids})
        return [(row["id"], row["username"]) for row in result["usernames"]]
