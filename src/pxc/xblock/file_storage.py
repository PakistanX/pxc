"""Django default_storage-backed FileStorage for PXC XBlock."""

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from pxc.lib.file_storage import FileStorage, FileStorageError


class DjangoFileStorage(FileStorage):
    """FileStorage backed by Django's default_storage (local, S3, GCS, etc.)."""

    def __init__(self, base_path: str) -> None:
        self._base = base_path.rstrip("/")

    def _path(self, path: str) -> str:
        clean = path.lstrip("/")
        return f"{self._base}/{clean}" if self._base else clean

    def mkdir(self, path: str) -> None:
        pass  # object storage has no real directories; local storage creates on write

    def read(self, path: str) -> bytes:
        full = self._path(path)
        if not default_storage.exists(full):
            raise FileStorageError(f"File not found: {path!r}")
        with default_storage.open(full) as f:
            return f.read()  # type: ignore[no-any-return]

    def write(self, path: str, content: bytes) -> None:
        full = self._path(path)
        if default_storage.exists(full):
            default_storage.delete(full)
        default_storage.save(full, ContentFile(content))

    def exists(self, path: str) -> bool:
        return default_storage.exists(self._path(path))  # type: ignore[no-any-return]

    def list(self, path: str) -> tuple[list[str], list[str]]:
        full = self._path(path)
        try:
            # Django returns (dirs, files); our ABC expects (files, dirs).
            dirs, files = default_storage.listdir(full)
        except OSError as e:
            raise FileStorageError(f"Directory not found: {path!r}") from e
        return sorted(files), sorted(dirs)

    def delete(self, path: str) -> bool:
        full = self._path(path)
        if default_storage.exists(full):
            default_storage.delete(full)
            return True
        # Attempt directory deletion by listing and recursing.
        try:
            dirs, files = default_storage.listdir(full)
        except OSError:
            return False
        for f in files:
            default_storage.delete(f"{full}/{f}")
        for d in dirs:
            self.delete(f"{path}/{d}")
        return True
