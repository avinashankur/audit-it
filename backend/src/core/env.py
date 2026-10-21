"""Runtime settings loaded from .env or environment."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.core.exceptions import ConfigurationError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    APP_NAME: str = "AuditIt"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_JSON_FORMAT: bool = False

    # Graph backend
    DEFAULT_GRAPH_BACKEND: Literal["networkx", "neo4j"] = "networkx"
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: SecretStr | None = None
    NEO4J_DATABASE: str = "neo4j"

    # BYOK model keys
    GEMINI_API_KEY: SecretStr | None = None
    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None

    # Chunking
    DEFAULT_CHUNK_SIZE: int = Field(default=800, ge=100, le=4000)
    DEFAULT_CHUNK_OVERLAP: int = Field(default=150, ge=0, le=500)

    # Retrieval
    TOP_K_CHUNKS: int = Field(default=5, ge=1, le=50)
    MAX_GRAPH_HOPS: int = Field(default=2, ge=1, le=5)

    # Ingestion and Upload limits
    MAX_UPLOAD_SIZE_MB: int = Field(default=50, ge=1, le=500)
    MAX_ACTIVE_INGEST_JOBS: int = Field(default=8, ge=1, le=64)

    def get_api_key(self, provider: str) -> str | None:
        key_map = {
            "gemini": self.GEMINI_API_KEY,
            "google": self.GEMINI_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "anthropic": self.ANTHROPIC_API_KEY,
            "claude": self.ANTHROPIC_API_KEY,
        }
        secret = key_map.get(provider.strip().lower())
        return secret.get_secret_value() if secret else None

    def is_provider_configured(self, provider: str) -> bool:
        key = self.get_api_key(provider)
        return bool(key and key.strip())

    def validate_for_provider(self, provider: str) -> None:
        if not self.is_provider_configured(provider):
            raise ConfigurationError(
                f"Mising API key for {provider}. Set {provider.upper()}_API_KEY in .env or via UI.",
                details={"provider": provider},
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
