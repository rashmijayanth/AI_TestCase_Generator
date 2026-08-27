from pathlib import Path

import pytest

from testgen.platform.storage import LocalFilesystemStorage, get_storage


@pytest.mark.unit
def test_put_get_exists_round_trip(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(str(tmp_path))

    assert storage.exists("a/b/c.txt") is False

    storage.put("a/b/c.txt", b"hello world")

    assert storage.exists("a/b/c.txt") is True
    assert storage.get("a/b/c.txt") == b"hello world"


@pytest.mark.unit
def test_rejects_path_traversal_keys(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(str(tmp_path))

    with pytest.raises(ValueError, match="escapes storage root"):
        storage.put("../../etc/passwd", b"malicious")


@pytest.mark.unit
def test_get_storage_returns_local_backend_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path))

    storage = get_storage()

    assert isinstance(storage, LocalFilesystemStorage)


@pytest.mark.unit
def test_get_storage_raises_for_s3_not_yet_implemented(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")

    with pytest.raises(NotImplementedError):
        get_storage()
