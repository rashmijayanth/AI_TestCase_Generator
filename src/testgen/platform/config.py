"""Application configuration, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "staging", "prod"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://testgen:changeme@localhost:5432/testgen"

    redis_url: str = "redis://localhost:6379/0"

    # pymilvus itself reads a real OS env var literally named MILVUS_URI for
    # its own internal connection default (confirmed by reading
    # pymilvus.orm.connections' source) -- colliding with the env var
    # pydantic-settings would otherwise auto-derive from this field's name.
    # Only surfaces where MILVUS_URI becomes a real process env var (e.g. a
    # container's `environment:`/`env_file:`, not this app's own .env-file
    # loading) -- confirmed live via `docker compose up`, where it broke both
    # the api and worker containers at import time. Renamed the env var, not
    # the Python attribute, so every existing `settings.milvus_uri` call site
    # stays unchanged.
    milvus_uri: str = Field(default="./data/milvus_lite.db", validation_alias="MILVUS_DB_URI")

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_model_pro: str = "gemini-1.5-pro"
    gemini_embedding_model: str = "text-embedding-004"

    # Obviously-a-placeholder default so local dev/tests work with zero setup,
    # but so it's unmistakable this must be overridden for staging/prod.
    jwt_secret_key: str = "dev-insecure-secret-change-in-production"
    jwt_expire_hours: int = 8

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""
    jira_issue_type: str = "Task"

    # Azure DevOps and Polarion have no live tenant available (DESIGN.md §8) --
    # these exist so a real deployment could configure them, not because this
    # environment ever connects live. See testgen.integrations.
    ado_organization: str = ""
    ado_project: str = ""
    ado_pat: str = ""

    polarion_base_url: str = ""
    polarion_project_id: str = ""
    polarion_token: str = ""

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "./data/storage"
    s3_bucket: str = ""
    aws_region: str = ""

    otel_exporter_otlp_endpoint: str = ""

    # The Streamlit UI is a separate process that talks to the API only over
    # HTTP (DESIGN.md §6) -- never imports testgen.api directly -- so it needs
    # the API's base URL, not just an in-process app object.
    api_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
