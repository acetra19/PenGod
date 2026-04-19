"""Application settings (Qdrant, optional API keys)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load from environment / `.env` for local development."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    qdrant_url: str = Field(default="http://localhost:6333", description="Qdrant HTTP endpoint")
    qdrant_api_key: str | None = Field(default=None, description="Optional API key for Qdrant Cloud")
    qdrant_collection: str = Field(default="h1_disclosures", description="Default collection name")
    qdrant_strict: bool = Field(
        default=False,
        description="If true, fail API startup when Qdrant is unreachable",
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        description="FastEmbed model id (must match embedding_vector_size)",
    )
    embedding_vector_size: int = Field(
        default=384,
        description="Vector dimension for the chosen embedding model",
    )
    chunk_size: int = Field(default=1200, ge=200, le=8000, description="Max chars per chunk")
    chunk_overlap: int = Field(default=150, ge=0, le=2000, description="Char overlap between chunks")
    pengod_api_key: str | None = Field(
        default=None,
        description="If set, engagement endpoints require header X-API-Key",
    )
    probe_timeout_seconds: float = Field(default=12.0, ge=2.0, le=60.0)
    probe_max_redirects: int = Field(default=5, ge=0, le=15)


def get_settings() -> Settings:
    return Settings()
