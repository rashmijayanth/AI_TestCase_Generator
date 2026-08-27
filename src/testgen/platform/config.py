"""Application configuration, loaded from environment variables / .env."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["local", "test", "staging", "prod"] = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://testgen:changeme@localhost:5432/testgen"

    redis_url: str = "redis://localhost:6379/0"

    milvus_uri: str = "./data/milvus_lite.db"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_model_pro: str = "gemini-1.5-pro"
    gemini_embedding_model: str = "text-embedding-004"

    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_path: str = "./data/storage"
    s3_bucket: str = ""
    aws_region: str = ""

    otel_exporter_otlp_endpoint: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
