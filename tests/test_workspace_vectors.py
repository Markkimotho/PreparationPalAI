from unittest.mock import patch
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from app.config import get_base_settings
from app.workspace import workspace_id
from app.vectorstore import get_vectorstore, clear_vectorstore, _workspace_stores


class LocalEmbeddings(Embeddings):
    def embed_documents(self, texts):
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text):
        return [1.0, 0.0, 0.0]


def test_real_vector_queries_and_delete_are_workspace_scoped(tmp_path, monkeypatch):
    monkeypatch.setattr(get_base_settings(), 'chroma_persist_dir', str(tmp_path / 'vectors'))
    with patch('app.vectorstore.get_embeddings', return_value=LocalEmbeddings()):
        alice = workspace_id.set('vector-alice')
        try:
            a = get_vectorstore()
            a.add_documents([Document(page_content='Alice secret', metadata=dict(source='alice.pdf', page=1))])
            bob = workspace_id.set('vector-bob')
            try:
                b = get_vectorstore()
                assert b.similarity_search('secret') == []
                b.add_documents([Document(page_content='Bob note', metadata=dict(source='bob.pdf', page=1))])
                assert b.similarity_search('note')[0].metadata['source'] == 'bob.pdf'
                clear_vectorstore()
            finally:
                workspace_id.reset(bob)
            assert a.similarity_search('secret')[0].metadata['source'] == 'alice.pdf'
        finally:
            workspace_id.reset(alice)
            _workspace_stores.pop('vector-alice', None)
            _workspace_stores.pop('vector-bob', None)
