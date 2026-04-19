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
        description="If set, protected POST /v1/* routes require header X-API-Key",
    )
    probe_timeout_seconds: float = Field(default=12.0, ge=2.0, le=60.0)
    probe_max_redirects: int = Field(default=5, ge=0, le=15)
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Ollama HTTP API for Strategist agent",
    )
    strategist_model: str = Field(default="llama3:latest", description="Ollama model id for Strategist")
    strategist_rag_limit: int = Field(default=10, ge=1, le=25, description="RAG hits passed to Strategist")
    strategist_max_user_chars: int = Field(
        default=12000,
        ge=2000,
        le=50000,
        description="Cap JSON user message size for Ollama (RAM on small VPS)",
    )
    strategist_ollama_num_ctx: int = Field(
        default=4096,
        ge=512,
        le=131072,
        description="Ollama num_ctx (KV cache); lower helps 8GB RAM hosts",
    )
    strategist_ollama_num_predict: int = Field(
        default=1536,
        ge=128,
        le=32768,
        description="Max new tokens for Strategist reply",
    )


def get_settings() -> Settings:
    return Settings()
