from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from app.workspace import workspace_id

# Curated list of supported Ollama chat models, shown in this order in the UI.
# Best open-source models for structured reasoning and JSON output as of 2026.
SUPPORTED_MODELS: list[str] = [
    "qwen2.5:7b",       # Best structured/JSON output — default for quiz generation
    "llama3.1:8b",      # Strong reasoning, supports tool calling
    "mistral",          # Solid all-rounder
    "gemma2:9b",        # Google quality, good responses
    "deepseek-r1:7b",   # Strong reasoning (R1 distil)
    "llama3.2:3b",      # Lightweight / fast option
    "llama3.2:1b",      # Fastest / lowest memory
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Ollama (local, free)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "nomic-embed-text"
    # Keep the model resident in memory between requests to avoid cold-load
    # latency. "30m" keeps it warm for 30 min after the last call; "-1" = forever.
    ollama_keep_alive: str = "30m"

    # ChromaDB (local, free)
    chroma_persist_dir: str = "data/chroma"
    chroma_collection_name: str = "rag-chatbot"

    # RAG tuning
    chunk_size: int = 1000
    chunk_overlap: int = 200
    top_k: int = 5
    memory_window: int = 10

    # Quiz / exam prep
    quiz_default_n: int = 10
    quiz_top_k: int = 8

    # Ingestion throughput — embeddings are the bottleneck for large files.
    # Chunks per embedding batch, and how many batches to embed concurrently.
    ingest_batch_size: int = 256
    ingest_workers: int = 4

    # Flashcards persisted store (mount a volume here in Docker to keep decks).
    flashcards_dir: str = "data/flashcards"
    coach_db: str = "data/coach/sessions.sqlite3"
    glm_model: str = "glm4:9b"
    deepseek_model: str = "deepseek-r1:7b"
    extra_models: list[str] = []
    public_base_url: str = ""
    social_image: str = "/social-preview.png"
    production: bool = False
    auth_enabled: bool = False
    # SHA-256 bearer token digests -> {workspace, role}. Never store raw tokens.
    auth_tokens: dict[str, dict[str, str]] = Field(default_factory=dict, repr=False)

    @model_validator(mode='after')
    def validate_security(self):
        import re
        if self.production and not self.auth_enabled:
            raise ValueError('PRODUCTION requires AUTH_ENABLED=true')
        if self.auth_enabled and not self.auth_tokens:
            raise ValueError('AUTH_TOKENS must contain at least one token digest')
        for digest, principal in self.auth_tokens.items():
            if not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise ValueError('AUTH_TOKENS keys must be SHA-256 hex digests')
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', principal.get('workspace', '')):
                raise ValueError('Each token requires a safe workspace identifier')
            if principal.get('workspace') == 'local':
                raise ValueError('The local workspace is reserved for unauthenticated local use')
            if principal.get('role') not in ('reader', 'editor', 'admin'):
                raise ValueError('Token role must be reader, editor or admin')
        return self


@lru_cache
def get_base_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    settings = get_base_settings()
    workspace = workspace_id.get()
    if workspace == 'local':
        return settings
    return settings.model_copy(update={
        'chroma_persist_dir': str(Path(settings.chroma_persist_dir) / 'workspaces' / workspace),
        'flashcards_dir': str(Path(settings.flashcards_dir) / 'workspaces' / workspace),
        'coach_db': str(Path(settings.coach_db).parent / 'workspaces' / workspace / 'sessions.sqlite3'),
    })
