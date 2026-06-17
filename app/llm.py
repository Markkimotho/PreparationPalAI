"""Bounded local inference defaults shared by every model-backed feature."""
import httpx
from langchain_core.messages import SystemMessage
from app.prompts import UNTRUSTED_CONTEXT
from langchain_ollama import ChatOllama as _ChatOllama
from app.config import get_settings


class GuardedChatOllama(_ChatOllama):
    def _convert_input(self, value):
        prompt = super()._convert_input(value)
        from langchain_core.prompt_values import ChatPromptValue
        return ChatPromptValue(messages=[SystemMessage(content=UNTRUSTED_CONTEXT), *prompt.to_messages()])


def ChatOllama(**kwargs):
    settings = get_settings()
    kwargs['num_ctx'] = min(kwargs.get('num_ctx', settings.llm_context_tokens), settings.llm_context_tokens)
    kwargs['num_predict'] = min(kwargs.get('num_predict', settings.llm_output_tokens), settings.llm_output_tokens)
    kwargs['client_kwargs'] = {'timeout': httpx.Timeout(settings.llm_timeout, connect=5)}
    return GuardedChatOllama(**kwargs)
