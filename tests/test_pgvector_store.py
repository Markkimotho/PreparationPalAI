import hashlib
import re

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from app import purge, vectorstore
from app.config import get_base_settings
from app.pgvector_store import DIMENSIONS, PgVectorStore
from app.workspace import workspace_id

pytestmark = pytest.mark.usefixtures('pg')


class HashEmbeddings(Embeddings):
    """Deterministic bag-of-words vectors: texts sharing words are close, unrelated texts are not."""

    def vector(self, text: str) -> list[float]:
        v = [0.0] * DIMENSIONS
        for word in re.findall(r'[a-z]+', text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % DIMENSIONS] += 1.0
        return v

    def embed_documents(self, texts):
        return [self.vector(t) for t in texts]

    def embed_query(self, text):
        return self.vector(text)


@pytest.fixture(autouse=True)
def postgres_mode(monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'storage_backend', 'postgres')
    monkeypatch.setattr('app.vectorstore.get_embeddings', lambda: HashEmbeddings())
    monkeypatch.setattr('app.pgvector_store.get_embeddings', lambda: HashEmbeddings())


def doc(text, source='notes.pdf', page=1, id=None, **meta):
    return Document(page_content=text, metadata=dict(source=source, page=page, id=id or hashlib.md5(text.encode()).hexdigest()[:12], **meta))


def as_user(workspace):
    return workspace_id.set(workspace)


def test_get_vectorstore_is_scoped_to_the_current_workspace_and_embedding_model():
    token = as_user('u-aaa')
    try:
        store = vectorstore.get_vectorstore()
    finally:
        workspace_id.reset(token)
    assert isinstance(store, PgVectorStore) and store.workspace == 'u-aaa' and store.collection == get_base_settings().chroma_collection_name


def test_search_returns_the_most_relevant_chunks_first():
    token = as_user('u-aaa')
    try:
        store = vectorstore.get_vectorstore()
        store.add_documents([doc('Newton second law force equals mass times acceleration'), doc('The Krebs cycle produces energy in cells'),
                             doc('Photosynthesis converts light into chemical energy')])
        found = store.similarity_search('force and acceleration of a mass', k=2)
    finally:
        workspace_id.reset(token)
    assert found[0].page_content.startswith('Newton') and found[0].metadata['source'] == 'notes.pdf' and found[0].metadata['page'] == 1


def test_the_retriever_the_app_uses_works_against_postgres():
    from app.retriever import get_retriever
    token = as_user('u-aaa')
    try:
        vectorstore.get_vectorstore().add_documents([doc('Ohm law voltage equals current times resistance'), doc('Mitochondria make energy')])
        results = get_retriever(top_k=2).invoke('voltage current resistance')
    finally:
        workspace_id.reset(token)
    assert [d.page_content for d in results] == ['Ohm law voltage equals current times resistance']      # lexical admission still applies


def test_other_learners_never_see_my_chunks_even_with_identical_text():
    text = 'The secret exam answer is photosynthesis'
    for user in ('u-alice', 'u-bob'):
        token = as_user(user)
        try:
            vectorstore.get_vectorstore().add_documents([doc(text, source=f'{user}.pdf', id='same-id')])
        finally:
            workspace_id.reset(token)
    token = as_user('u-bob')
    try:
        found = vectorstore.get_vectorstore().similarity_search('secret exam answer', k=10)
        assert [d.metadata['source'] for d in found] == ['u-bob.pdf']
        vectorstore.clear_vectorstore()
        assert vectorstore.get_doc_count() == 0
    finally:
        workspace_id.reset(token)
    token = as_user('u-alice')
    try:
        assert vectorstore.get_doc_count() == 1 and vectorstore.list_sources() == [{'source': 'u-alice.pdf', 'chunks': 1, 'type': 'pdf'}]
    finally:
        workspace_id.reset(token)


def test_search_still_fills_k_when_many_other_learners_share_the_table():
    # At this size Postgres uses an exact btree plan; hnsw.iterative_scan keeps the HNSW plan correct for a very large tenant.
    for n in range(30):
        token = as_user(f'u-crowd-{n}')
        try:
            vectorstore.get_vectorstore().add_documents([doc(f'common words about physics and chemistry number {i}', id=f'{n}-{i}') for i in range(20)])
        finally:
            workspace_id.reset(token)
    token = as_user('u-crowd-7')
    try:
        found = vectorstore.get_vectorstore().similarity_search('physics and chemistry', k=10)
    finally:
        workspace_id.reset(token)
    assert len(found) == 10 and {d.metadata['id'].split('-')[0] for d in found} == {'7'}


def test_ingest_skips_known_chunks_and_updates_changed_ones():
    token = as_user('u-aaa')
    try:
        chunks = [doc('alpha beta gamma', id='c1'), doc('delta epsilon', id='c2')]
        assert vectorstore.ingest_documents(chunks) == 2
        assert vectorstore.ingest_documents(chunks) == 0                      # already indexed: nothing re-embedded
        vectorstore.get_vectorstore().add_documents([doc('alpha beta rewritten', id='c1')])
        assert vectorstore.get_doc_count() == 2
        assert 'rewritten' in vectorstore.get_vectorstore().similarity_search('rewritten', k=1)[0].page_content
    finally:
        workspace_id.reset(token)


def test_ingest_embeds_in_batches_across_threads():
    token = as_user('u-aaa')
    try:
        chunks = [doc(f'chunk number {i} about topic {i}', id=f'id-{i}') for i in range(25)]
        assert vectorstore.ingest_documents(chunks, batch_size=4, max_workers=3) == 25
        assert vectorstore.get_doc_count() == 25
    finally:
        workspace_id.reset(token)


def test_each_embedding_model_has_its_own_collection():
    token = as_user('u-aaa')
    try:
        one, two = PgVectorStore('u-aaa', 'rag--model-one', HashEmbeddings()), PgVectorStore('u-aaa', 'rag--model-two', HashEmbeddings())
        one.add_documents([doc('only in the first model')])
        assert (one.count(), two.count()) == (1, 0) and two.similarity_search('first model') == []
    finally:
        workspace_id.reset(token)


def test_a_wrong_sized_embedding_is_refused_clearly_and_stores_nothing():
    class Small(Embeddings):
        def embed_documents(self, texts):
            return [[1.0, 2.0, 3.0] for _ in texts]

        def embed_query(self, text):
            return [1.0, 2.0, 3.0]

    store = PgVectorStore('u-aaa', 'c', Small())
    with pytest.raises(ValueError, match='1024'):
        store.add_documents([doc('anything')])
    assert PgVectorStore('u-aaa', 'c', HashEmbeddings()).count() == 0


def test_purging_a_workspace_removes_only_its_chunks():
    for user in ('u-aaa', 'u-bbb'):
        token = as_user(user)
        try:
            vectorstore.get_vectorstore().add_documents([doc(f'{user} private note')])
        finally:
            workspace_id.reset(token)
    assert purge.purge_workspace('u-aaa')['vectors_postgres'] == 1
    token = as_user('u-bbb')
    try:
        assert vectorstore.get_doc_count() == 1
    finally:
        workspace_id.reset(token)


def test_readiness_counts_through_postgres():
    token = as_user('u-aaa')
    try:
        assert vectorstore.count_chunks() == 0
    finally:
        workspace_id.reset(token)
