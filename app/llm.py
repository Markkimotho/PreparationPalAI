"""Bounded local inference defaults shared by every model-backed feature."""
import httpx
from langchain_ollama import ChatOllama as _ChatOllama
from app.config import get_settings


def ChatOllama(**kwargs):
    settings = get_settings()
    kwargs['num_ctx'] = min(kwargs.get('num_ctx', settings.llm_context_tokens), settings.llm_context_tokens)
    kwargs['num_predict'] = min(kwargs.get('num_predict', settings.llm_output_tokens), settings.llm_output_tokens)
    kwargs['client_kwargs'] = {'timeout': httpx.Timeout(settings.llm_timeout, connect=5)}
    return _ChatOllama(**kwargs)
