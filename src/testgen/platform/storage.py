"""StoragePort: local filesystem for dev, S3 for prod (DESIGN.md §7), same interface."""

from pathlib import Path
from typing import Protocol

from testgen.platform.config import Settings, get_settings


class StoragePort(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...


class LocalFilesystemStorage:
    def __init__(self, root: str) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        root = self._root.resolve()
        path = (root / key).resolve()
        if path != root and root not in path.parents:
            raise ValueError(f"Storage key escapes storage root: {key!r}")
        return path

    def put(self, key: str, data: bytes) -> None:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()


def get_storage(settings: Settings | None = None) -> StoragePort:
    settings = settings or get_settings()
    if settings.storage_backend == "local":
        return LocalFilesystemStorage(settings.storage_local_path)
    raise NotImplementedError(
        "S3 storage is planned (DESIGN.md §7, Infra phase) but not yet implemented — "
        "set STORAGE_BACKEND=local."
    )
