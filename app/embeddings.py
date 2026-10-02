from functools import lru_cache

from langchain_ollama import OllamaEmbeddings

from app.config import get_settings
import httpx


@lru_cache
def get_embeddings() -> OllamaEmbeddings:
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embedding_model,
        base_url=settings.ollama_base_url,
        client_kwargs={'timeout': httpx.Timeout(settings.llm_timeout, connect=5)},
    )
