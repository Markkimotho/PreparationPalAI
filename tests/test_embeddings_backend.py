import math

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import SecretStr

from app import vectorstore
from app.config import get_base_settings
from app.embeddings import GatewayEmbeddings, collection_name, get_embeddings
from app.llm import ModelServiceUnavailable
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


class ThreeDim(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


def test_gateway_embeddings_record_usage_and_identify_the_workspace(gateway):
    token = workspace_id.set('class-a')
    try:
        with metering_scope('kb_ingest', 'req-1') as meter:
            vectors = get_embeddings().embed_documents(['alpha', 'beta'])
    finally:
        workspace_id.reset(token)
    assert [len(v) for v in vectors] == [8, 8]
    assert [(r.alias, r.purpose, r.input_tokens, r.output_tokens, r.estimated) for r in meter.records] == [
        ('embed-default', 'embed', 10, 0, False)]
    body = gateway.requests[0]['body']
    assert body['model'] == 'embed-default' and body['user'] == 'class-a'


def test_missing_embedding_usage_is_estimated(gateway):
    gateway.usage = None
    with metering_scope('kb_ingest', 'req-2') as meter:
        GatewayEmbeddings().embed_query('x' * 40)
    assert meter.records[0].estimated is True and meter.records[0].input_tokens == math.ceil(40 / 4)


def test_large_batches_are_split_into_bounded_requests(gateway):
    GatewayEmbeddings().embed_documents([f'text {i}' for i in range(150)])
    sizes = [len(r['body']['input']) for r in gateway.requests]
    assert sizes == [64, 64, 22]


def test_dimensions_are_requested_only_when_configured(gateway, monkeypatch):
    GatewayEmbeddings().embed_query('a')
    assert 'dimensions' not in gateway.requests[-1]['body']
    monkeypatch.setattr(get_base_settings(), 'embedding_dimensions', 1024)
    GatewayEmbeddings().embed_query('a')
    assert gateway.requests[-1]['body']['dimensions'] == 1024


def test_gateway_failure_is_unavailable_not_a_crash(gateway):
    gateway.status = 500
    with pytest.raises(ModelServiceUnavailable):
        GatewayEmbeddings().embed_query('a')


def test_legacy_ollama_collection_still_read():
    assert collection_name() == get_base_settings().chroma_collection_name


def test_collection_name_differs_per_embedding_model(gateway, monkeypatch):
    settings = get_base_settings()
    base = settings.chroma_collection_name
    first = collection_name()
    assert first != base and first.startswith(base + '--') and 3 <= len(first) <= 63
    monkeypatch.setattr(settings, 'embedding_alias', 'embed-other')
    assert collection_name() != first
    monkeypatch.setattr(settings, 'embedding_dimensions', 1024)
    assert collection_name().endswith('-1024')


def test_switching_backend_does_not_mix_dimensions(tmp_path, monkeypatch):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'chroma_persist_dir', str(tmp_path / 'vectors'))
    monkeypatch.setattr(vectorstore, '_vectorstore', None)
    with monkeypatch.context() as m:
        m.setattr('app.vectorstore.get_embeddings', lambda: ThreeDim())
        vectorstore.get_vectorstore().add_documents([Document(page_content='old ollama note', metadata=dict(source='old.pdf', page=1))])
    monkeypatch.setattr(vectorstore, '_vectorstore', None)
    with FakeOpenAI() as fake:
        monkeypatch.setattr(settings, 'inference_backend', 'gateway')
        monkeypatch.setattr(settings, 'gateway_base_url', fake.url)
        monkeypatch.setattr(settings, 'gateway_api_key', SecretStr('k'))
        store = vectorstore.get_vectorstore()
        store.add_documents([Document(page_content='new gateway note', metadata=dict(source='new.pdf', page=1))])
        found = store.similarity_search('note')
    assert [d.metadata['source'] for d in found] == ['new.pdf']


def test_store_cache_follows_a_changed_embedding_model(tmp_path, gateway, monkeypatch):
    settings = get_base_settings()
    monkeypatch.setattr(settings, 'chroma_persist_dir', str(tmp_path / 'vectors'))
    monkeypatch.setattr(vectorstore, '_vectorstore', None)
    first = vectorstore.get_vectorstore()
    monkeypatch.setattr(settings, 'embedding_alias', 'embed-other')
    assert vectorstore.get_vectorstore()._collection.name != first._collection.name


def test_ingest_records_embedding_usage_from_worker_threads(tmp_path, gateway, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'chroma_persist_dir', str(tmp_path / 'vectors'))
    monkeypatch.setattr(vectorstore, '_vectorstore', None)
    docs = [Document(page_content=f'chunk {i}', metadata=dict(id=f'id-{i}', source='a.pdf', page=1)) for i in range(5)]
    with metering_scope('kb_ingest', 'req-9') as meter:
        added = vectorstore.ingest_documents(docs, batch_size=2, max_workers=3)
    assert added == 5
    assert sum(r.input_tokens for r in meter.records) == 25 and all(r.purpose == 'embed' for r in meter.records)
    assert {r['body']['user'] for r in gateway.requests} == {'local'}
