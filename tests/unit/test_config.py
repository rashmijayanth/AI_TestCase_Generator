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
