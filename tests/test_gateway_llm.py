import math

import pytest
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, SecretStr

from app.config import get_base_settings
from app.llm import GuardedChatOllama, ModelServiceUnavailable, chat_model
from app.metering import metering_scope
from app.workspace import workspace_id
from tests.support.fake_openai import FakeOpenAI


@pytest.fixture
def gateway(monkeypatch):
    with FakeOpenAI() as fake:
        settings = get_base_settings()
        monkeypatch.setattr(settings, 'inference_backend', 'gateway')
        monkeypatch.setattr(settings, 'gateway_base_url', fake.url)
        monkeypatch.setattr(settings, 'gateway_api_key', SecretStr('sk-test'))
        yield fake


SCHEMA = {'type': 'object', 'properties': {'answer': {'type': 'string'}}, 'required': ['answer']}


def ask(model='open-default', text='What is force?', **kwargs):
    return chat_model(model=model, **kwargs).invoke([HumanMessage(content=text)])


def test_schema_maps_to_response_format(gateway):
    ask(format=SCHEMA)
    body = gateway.chat_requests('open-default')[0]
    assert body['response_format']['type'] == 'json_schema'
    assert body['response_format']['json_schema']['schema'] == SCHEMA


def test_invoke_time_format_maps_to_response_format(gateway):
    chat_model(model='open-default').invoke([HumanMessage(content='hi')], format=SCHEMA)
    body = gateway.chat_requests('open-default')[0]
    assert body['response_format']['json_schema']['schema'] == SCHEMA
    assert 'format' not in body


def cap(body):
    return body.get('max_completion_tokens', body.get('max_tokens'))


def test_num_predict_maps_to_bounded_max_tokens(gateway):
    ask(num_predict=999_999)
    assert cap(gateway.chat_requests('open-default')[0]) == get_base_settings().llm_output_tokens
    ask(num_predict=100)
    assert cap(gateway.chat_requests('open-default')[1]) == 100


def test_sends_bearer_key_user_and_correlation_metadata(gateway):
    token = workspace_id.set('class-a')
    try:
        with metering_scope('quiz_generate', 'req-42'):
            ask()
    finally:
        workspace_id.reset(token)
    request = [r for r in gateway.requests if r['body']['model'] == 'open-default'][0]
    assert request['auth'] == 'Bearer sk-test'
    assert request['body']['user'] == 'class-a'
    assert request['body']['metadata'] == {'spend_logs_metadata': {'action': 'quiz_generate', 'request_id': 'req-42'}}


def test_records_main_and_guard_usage(gateway):
    with metering_scope('chat', 'req-1') as meter:
        ask()
    by_purpose = {}
    for r in meter.records:
        by_purpose.setdefault(r.purpose, []).append(r)
    assert [(r.alias, r.input_tokens, r.output_tokens, r.estimated) for r in by_purpose['main']] == [('open-default', 11, 7, False)]
    assert len(by_purpose['guard']) == 2  # input check and output check
    assert {r.alias for r in by_purpose['guard']} == {'guard'}


def test_missing_usage_is_estimated(gateway):
    gateway.usage = None
    gateway.default_reply = 'hello'
    with metering_scope('chat', 'req-2') as meter:
        ask(text='x' * 40)
    main = [r for r in meter.records if r.purpose == 'main'][0]
    assert main.estimated is True
    assert main.output_tokens == math.ceil(len('hello') / 4)
    assert main.input_tokens >= 10  # at least the 40 user characters / 4


@pytest.mark.parametrize('status', [500, 502, 429])
def test_gateway_error_raises_unavailable_and_records_nothing(gateway, status):
    gateway.status = status
    with metering_scope('chat', 'req-3') as meter:
        with pytest.raises(ModelServiceUnavailable, match='The model service is unavailable. Please retry.'):
            ask()
    assert meter.records == []


def test_gateway_unreachable_raises_unavailable(monkeypatch, gateway):
    monkeypatch.setattr(get_base_settings(), 'gateway_base_url', 'http://127.0.0.1:1')
    with pytest.raises(ModelServiceUnavailable):
        ask()


def test_invalid_json_triggers_generation_retry(gateway):
    from app.generation import validated_batches

    class Item(BaseModel):
        q: str

    class Batch(BaseModel):
        items: list[Item]

    gateway.replies = ['not json', '{"items": [{"q": "What is F?"}]}']

    def parse(text):
        import json
        return json.loads(text)

    with metering_scope('quiz_generate', 'req-5') as meter:
        items = validated_batches(chat_model(model='open-default'), lambda *a: 'make one', parse, Batch, 1, 'items', 'q')
    assert items == [{'q': 'What is F?'}]
    assert len([r for r in meter.records if r.purpose == 'main']) == 2


def test_length_finish_reason_is_rejected_as_truncated(gateway):
    from app.generation import validated_batches

    class Batch(BaseModel):
        items: list[dict]

    class Truncated:
        content = '{"items": [{"q": "a"}]}'
        response_metadata = {'finish_reason': 'length'}

    class Llm:
        def invoke(self, *_a, **_k):
            return Truncated()

    with pytest.raises(ValueError, match='Output limit reached'):
        validated_batches(Llm(), lambda *a: 'x', __import__('json').loads, Batch, 1, 'items', 'q')


def test_ollama_backend_unchanged():
    model = chat_model(model='qwen2.5:7b')
    assert isinstance(model, GuardedChatOllama)
