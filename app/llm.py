"""Bounded local inference defaults shared by every model-backed feature."""
import httpx
from langchain_core.messages import SystemMessage
from app.prompts import UNTRUSTED_CONTEXT
from langchain_ollama import ChatOllama as _ChatOllama
from app.config import get_settings
from app.safety import moderate, verify_response


class GuardedChatOllama(_ChatOllama):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Check user/tool data as well as the final output. Suppress callbacks on
        # the raw inference so nested tool calls cannot leak unchecked tokens.
        text = '\n'.join(str(m.content) for m in messages if m.type != 'system')
        moderate(text, model=self.model, base_url=self.base_url,
                 timeout=get_settings().llm_timeout)
        result = super()._generate(messages, stop=stop, run_manager=None, **kwargs)
        for generation in result.generations:
            message = generation.message
            import json
            content = str(message.content) + json.dumps(message.tool_calls)
            moderate(content, model=self.model, base_url=self.base_url,
                     timeout=get_settings().llm_timeout)
            if not message.tool_calls:
                verify_response(messages, str(message.content), model=self.model,
                                base_url=self.base_url, timeout=get_settings().llm_timeout)
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


def ChatOllama(**kwargs):
    settings = get_settings()
    kwargs['num_ctx'] = min(kwargs.get('num_ctx', settings.llm_context_tokens), settings.llm_context_tokens)
    kwargs['num_predict'] = min(kwargs.get('num_predict', settings.llm_output_tokens), settings.llm_output_tokens)
    kwargs['client_kwargs'] = {'timeout': httpx.Timeout(settings.llm_timeout, connect=5)}
    return GuardedChatOllama(**kwargs)
