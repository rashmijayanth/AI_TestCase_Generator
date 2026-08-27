from pathlib import Path

import pytest

from testgen.platform.config import Settings


@pytest.mark.unit
def test_defaults_are_sane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # guarantees no ambient .env influences defaults

    settings = Settings()

    assert settings.app_env == "local"
    assert settings.gemini_model == "gemini-2.0-flash"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.storage_backend == "local"


@pytest.mark.unit
def test_env_var_overrides_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")

    settings = Settings()

    assert settings.app_env == "prod"
    assert settings.gemini_api_key == "test-key-123"


@pytest.mark.unit
def test_milvus_db_uri_env_var_is_read_and_the_colliding_name_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pymilvus itself reads a real OS env var literally named MILVUS_URI for
    its own connection default (confirmed by reading pymilvus.orm.connections'
    source, and by a real MILVUS_URI/`ConnectionConfigException` crash inside
    the api/worker containers -- see docs/PROGRESS.md). settings.milvus_uri
    must keep reading MILVUS_DB_URI, not the name pymilvus has already claimed.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MILVUS_URI", "http://should-not-be-read:19530")
    monkeypatch.setenv("MILVUS_DB_URI", "/custom/milvus_lite.db")

    settings = Settings()

    assert settings.milvus_uri == "/custom/milvus_lite.db"
