"""FileStorage implementation that proxies every operation back to pxc-xblock.

Files live behind Django's `default_storage` (S3 in production) on the
xblock/LMS side. Rather than duplicating S3 credentials into this service,
every read/write is a synchronous HTTP callback that reuses the existing
`DjangoFileStorage` adapter unchanged.
"""

import base64

from pxc.lib.file_storage import FileStorage, FileStorageError
from pxc.libserver import client


class HttpFileStorage(FileStorage):
    """FileStorage backed by HTTP callbacks to pxc.xblock's internal API.

    ``activity_id`` mirrors the scoping ``DjangoFileStorage(f"pxc/{activity_id}/storage")``
    already applies on the xblock side — it's forwarded on every call so the
    callback can reconstruct the same scoped storage root.
    """

    def __init__(self, activity_id: str) -> None:
        self._activity_id = activity_id

    def mkdir(self, path: str) -> None:
        pass  # object storage has no real directories; matches DjangoFileStorage

    def read(self, path: str) -> bytes:
        try:
            result = client.post(
                "/storage/read",
                {"activity_id": self._activity_id, "path": path},
            )
        except client.InternalApiError as e:
            raise FileStorageError(str(e)) from e
        return base64.b64decode(result["content_b64"])

    def write(self, path: str, content: bytes) -> None:
        try:
            client.post(
                "/storage/write",
                {
                    "activity_id": self._activity_id,
                    "path": path,
                    "content_b64": base64.b64encode(content).decode("ascii"),
                },
            )
        except client.InternalApiError as e:
            raise FileStorageError(str(e)) from e

    def exists(self, path: str) -> bool:
        result = client.post(
            "/storage/exists",
            {"activity_id": self._activity_id, "path": path},
        )
        return bool(result["exists"])

    def list(self, path: str) -> tuple[list[str], list[str]]:
        try:
            result = client.post(
                "/storage/list",
                {"activity_id": self._activity_id, "path": path},
            )
        except client.InternalApiError as e:
            raise FileStorageError(str(e)) from e
        return result["files"], result["directories"]

    def delete(self, path: str) -> bool:
        result = client.post(
            "/storage/delete",
            {"activity_id": self._activity_id, "path": path},
        )
        return bool(result["deleted"])
