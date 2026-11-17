"""Embeddings for the configured backend, plus the vector collection that matches them.

Vectors from different embedding models are not comparable (and often differ in
dimension), so each gateway embedding model gets its own collection.
"""
import math
import re
from functools import lru_cache

import httpx
import openai
from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings

from app.config import get_settings
from app.llm import ModelServiceUnavailable
from app.metering import UsageRecord, record
from app.workspace import request_id as http_request_id, workspace_id
from app.metering import current_action

BATCH = 64  # inputs per gateway request


class GatewayEmbeddings(Embeddings):
    def __init__(self):
        settings = get_settings()
        self.alias = settings.embedding_alias
        self.dimensions = settings.embedding_dimensions
        self.client = openai.OpenAI(base_url=f'{settings.gateway_base_url.rstrip("/")}/v1',
                                    api_key=settings.gateway_api_key.get_secret_value(),
                                    timeout=settings.llm_timeout, max_retries=0)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), BATCH):
            vectors.extend(self._embed(texts[start:start + BATCH]))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, batch: list[str]) -> list[list[float]]:
        action, request_id = current_action() or ('unscoped', http_request_id.get())
        extra = {'dimensions': self.dimensions} if self.dimensions else {}
        try:
            response = self.client.embeddings.create(
                model=self.alias, input=batch, user=workspace_id.get(), encoding_format='float',
                extra_body={'metadata': {'spend_logs_metadata': {'action': action, 'request_id': request_id}}}, **extra)
        except (openai.OpenAIError, httpx.HTTPError) as exc:
            raise ModelServiceUnavailable() from exc
        used = getattr(response, 'usage', None)
        if used is not None and getattr(used, 'prompt_tokens', None) is not None:
            record(UsageRecord(self.alias, 'embed', int(used.prompt_tokens), 0, False))
        else:
            record(UsageRecord(self.alias, 'embed', math.ceil(sum(len(t) for t in batch) / 4), 0, True))
        return [item.embedding for item in sorted(response.data, key=lambda d: d.index)]


@lru_cache
def _ollama_embeddings(model: str, base_url: str, timeout: float) -> OllamaEmbeddings:
    return OllamaEmbeddings(model=model, base_url=base_url, client_kwargs={'timeout': httpx.Timeout(timeout, connect=5)})


def get_embeddings() -> Embeddings:
    settings = get_settings()
    if settings.inference_backend == 'gateway':
        return GatewayEmbeddings()
    return _ollama_embeddings(settings.ollama_embedding_model, settings.ollama_base_url, settings.llm_timeout)


def collection_name() -> str:
    """Self-hosted data keeps its original collection; gateway collections encode the embedding model."""
    settings = get_settings()
    if settings.inference_backend != 'gateway':
        return settings.chroma_collection_name
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', settings.embedding_alias).strip('-')
    dims = f'-{settings.embedding_dimensions}' if settings.embedding_dimensions else ''
    return f'{settings.chroma_collection_name}--{slug}{dims}'[:63].strip('-_.')
