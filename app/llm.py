"""Bounded inference defaults shared by every model-backed feature.

Two backends sit behind one factory, `chat_model`:
  * ollama  - self-hosted default (GuardedChatOllama)
  * gateway - OpenAI-compatible LiteLLM gateway (GuardedChatGateway)
Both run the same moderation and verification guards and record token usage with
`app.metering` so the billing layer can charge for what was actually used.
"""
import json
import logging
import math

import httpx
import openai
from langchain_core.messages import SystemMessage
from langchain_ollama import ChatOllama as _ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config import get_settings
from app.metering import UsageRecord, current_action, record
from app.prompts import UNTRUSTED_CONTEXT
from app.safety import moderate, verify_response
from app.workspace import request_id as http_request_id, workspace_id

logger = logging.getLogger(__name__)


class ModelServiceUnavailable(RuntimeError):
    """The model gateway is down, erroring, or refusing us. Nothing was produced."""

    def __init__(self, message: str = 'The model service is unavailable. Please retry.'):
        super().__init__(message)


def _estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def record_response(message, alias: str, purpose: str, prompt_messages) -> None:
    """Record the usage of one model response; estimate from characters if the provider sent none."""
    meta = getattr(message, 'usage_metadata', None) or {}
    if meta.get('input_tokens') is not None and meta.get('output_tokens') is not None:
        record(UsageRecord(alias, purpose, int(meta['input_tokens']), int(meta['output_tokens']), False))
        return
    prompt = ''.join(str(m.content) for m in prompt_messages)
    produced = str(message.content) + json.dumps(getattr(message, 'tool_calls', None) or [])
    record(UsageRecord(alias, purpose, _estimate_tokens(prompt), _estimate_tokens(produced), True))


class _GuardMixin:
    """Moderate input and output, verify grounded answers, and meter every generation."""

    def _guard_args(self) -> dict:
        raise NotImplementedError

    def _alias(self) -> str:
        raise NotImplementedError

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Check user/tool data as well as the final output. Suppress callbacks on
        # the raw inference so nested tool calls cannot leak unchecked tokens.
        text = '\n'.join(str(m.content) for m in messages if m.type != 'system')
        moderate(text, **self._guard_args())
        result = super()._generate(messages, stop=stop, run_manager=None, **kwargs)
        for generation in result.generations:
            message = generation.message
            # Charge before any check can reject the output: the tokens were consumed.
            record_response(message, self._alias(), 'main', messages)
            content = str(message.content) + json.dumps(message.tool_calls)
            moderate(content, **self._guard_args())
            if not message.tool_calls:
                verify_response(messages, str(message.content), **self._guard_args())
        return result

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessageChunk
        from langchain_core.outputs import ChatGenerationChunk
        result = self._generate(messages, stop=stop, **kwargs)
        for generation in result.generations:
            msg = generation.message
            yield ChatGenerationChunk(message=AIMessageChunk(
                content=msg.content, tool_calls=msg.tool_calls,
                additional_kwargs=msg.additional_kwargs))

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        import asyncio
        return await asyncio.to_thread(self._generate, messages, stop=stop, **kwargs)

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessageChunk
        from langchain_core.outputs import ChatGenerationChunk
        result = await self._agenerate(messages, stop=stop, **kwargs)
        for generation in result.generations:
            msg = generation.message
            yield ChatGenerationChunk(message=AIMessageChunk(content=msg.content,
                tool_calls=msg.tool_calls, additional_kwargs=msg.additional_kwargs))

    def _convert_input(self, value):
        prompt = super()._convert_input(value)
        from langchain_core.prompt_values import ChatPromptValue
        return ChatPromptValue(messages=[SystemMessage(content=UNTRUSTED_CONTEXT), *prompt.to_messages()])


class GuardedChatOllama(_GuardMixin, _ChatOllama):
    def _guard_args(self) -> dict:
        return dict(model=self.model, base_url=self.base_url, timeout=get_settings().llm_timeout)

    def _alias(self) -> str:
        return self.model


def response_format(schema: dict) -> dict:
    return {'type': 'json_schema', 'json_schema': {'name': 'response', 'schema': schema, 'strict': False}}


_PROVIDER_ERRORS = (openai.OpenAIError, httpx.HTTPError)


class _GatewayMixin:
    """OpenAI-compatible client details: format mapping, correlation, error mapping."""

    def _get_request_payload(self, input_, *, stop=None, **kwargs):
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        action, request_id = current_action() or ('unscoped', http_request_id.get())
        payload['user'] = workspace_id.get()
        payload['metadata'] = {'spend_logs_metadata': {'action': action, 'request_id': request_id}}
        return payload

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        schema = kwargs.pop('format', None)
        if schema is not None:
            kwargs['response_format'] = response_format(schema)
        try:
            return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        except _PROVIDER_ERRORS as exc:
            logger.error('Model gateway call failed', extra={'alias': getattr(self, 'model_name', '?'),
                         'status': getattr(exc, 'status_code', None), 'error': type(exc).__name__})
            raise ModelServiceUnavailable() from exc


class RawChatGateway(_GatewayMixin, ChatOpenAI):
    """Unguarded gateway model. Only the safety judge may use it; everything else is guarded."""


class GuardedChatGateway(_GuardMixin, _GatewayMixin, ChatOpenAI):
    def _guard_args(self) -> dict:
        settings = get_settings()
        return dict(model=settings.guard_alias, base_url=settings.gateway_base_url, timeout=settings.llm_timeout)

    def _alias(self) -> str:
        return self.model_name


def _bounded(kwargs: dict) -> dict:
    settings = get_settings()
    kwargs['num_ctx'] = min(kwargs.get('num_ctx', settings.llm_context_tokens), settings.llm_context_tokens)
    kwargs['num_predict'] = min(kwargs.get('num_predict', settings.llm_output_tokens), settings.llm_output_tokens)
    return kwargs


def _gateway_kwargs(model: str, kwargs: dict) -> dict:
    settings = get_settings()
    kwargs = _bounded(dict(kwargs))
    built = dict(model=model, base_url=f'{settings.gateway_base_url.rstrip("/")}/v1',
                 api_key=SecretStr(settings.gateway_api_key.get_secret_value()),
                 timeout=settings.llm_timeout, max_retries=0,  # the gateway owns retries and fallbacks
                 temperature=kwargs.get('temperature', 0), max_tokens=kwargs['num_predict'],
                 use_responses_api=False, stream_usage=True)
    if kwargs.get('format') is not None:
        built['model_kwargs'] = {'response_format': response_format(kwargs['format'])}
    return built


def chat_model(model: str | None = None, **kwargs):
    """The guarded chat model for the configured backend."""
    settings = get_settings()
    if settings.inference_backend == 'gateway':
        return GuardedChatGateway(**_gateway_kwargs(model or settings.ollama_model, kwargs))
    if model is not None:
        kwargs['model'] = model
    kwargs = _bounded(kwargs)
    kwargs.setdefault('base_url', settings.ollama_base_url)
    kwargs.setdefault('keep_alive', settings.ollama_keep_alive)
    kwargs['client_kwargs'] = {'timeout': httpx.Timeout(settings.llm_timeout, connect=5)}
    return GuardedChatOllama(**kwargs)


def raw_chat_model(model: str, **kwargs):
    """Unguarded gateway model for the safety judge. Ollama callers build their own."""
    return RawChatGateway(**_gateway_kwargs(model, kwargs))

