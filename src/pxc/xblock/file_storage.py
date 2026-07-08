"""Django default_storage-backed file storage for PXC XBlock.

Called from internal_api.py (HTTP callbacks from the standalone lib-server)
rather than injected into an in-process `ActivityRuntime` — pxc-xblock no
longer depends on pxc-lib, so this is a plain class, not an ABC subclass.

Targets Python 3.5 (Juniper-era Open edX): no f-strings, no
``from __future__ import annotations``, no bare generic subscripting.
"""

from typing import List, Tuple

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


class FileStorageError(Exception):
    """Raised on file storage access errors (path traversal, missing files, etc.)."""


class DjangoFileStorage(object):
    """File storage backed by Django's default_storage (local, S3, GCS, etc.)."""

    def __init__(self, base_path):
        # type: (str) -> None
        self._base = base_path.rstrip("/")

    def _path(self, path):
        # type: (str) -> str
        clean = path.lstrip("/")
        return "{0}/{1}".format(self._base, clean) if self._base else clean

    def mkdir(self, path):
        # type: (str) -> None
        pass  # object storage has no real directories; local storage creates on write

    def read(self, path):
        # type: (str) -> bytes
        full = self._path(path)
        if not default_storage.exists(full):
            raise FileStorageError("File not found: {0!r}".format(path))
        with default_storage.open(full) as f:
            return f.read()

    def write(self, path, content):
        # type: (str, bytes) -> None
        full = self._path(path)
        if default_storage.exists(full):
            default_storage.delete(full)
        default_storage.save(full, ContentFile(content))

    def exists(self, path):
        # type: (str) -> bool
        return default_storage.exists(self._path(path))

    def list(self, path):
        # type: (str) -> Tuple[List[str], List[str]]
        full = self._path(path)
        try:
            # Django returns (dirs, files); our callers expect (files, dirs).
            dirs, files = default_storage.listdir(full)
        except OSError as e:
            raise FileStorageError("Directory not found: {0!r}".format(path)) from e
        return sorted(files), sorted(dirs)

    def delete(self, path):
        # type: (str) -> bool
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
            default_storage.delete("{0}/{1}".format(full, f))
        for d in dirs:
            self.delete("{0}/{1}".format(path, d))
        return True
