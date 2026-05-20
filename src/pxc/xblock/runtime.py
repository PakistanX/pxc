from pathlib import Path

from django.contrib.auth import get_user_model

from pxc.lib.field_store import FieldStore
from pxc.lib.file_storage import FileStorage
from pxc.lib.permission import Permission
from pxc.lib.runtime import ActivityRuntime, SandboxContext


class XBlockActivityRuntime(ActivityRuntime):

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
        """Build the xblock `storage` handler URL for a file in scoped storage.

        The base class generates `/activity/{activity_id}/storage/{name}/...`,
        which is the notebook app's URL space. For the xblock we swap that
        prefix for the handler URL precomputed by `PxcXBlock._make_runtime` so
        the activity reaches our `storage` handler instead.
        """
        base = super().storage_url(name, path, context)
        prefix = f"/activity/{self._activity_id}/storage"
        return f"{self._storage_base_url}{base[len(prefix):]}"

    def get_usernames(self, ids: list[str]) -> list[tuple[str, str]]:
        User = get_user_model()
        return [(str(u.id), u.username) for u in User.objects.filter(id__in=ids).all()]
