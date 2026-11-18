"""Vector search on Postgres (pgvector) for hosted mode, scoped to one learner and one embedding model.

Every statement filters on `workspace` and `collection`, so one learner can never read, count or
delete another's chunks. `hnsw.iterative_scan` keeps filtered searches returning k results even
when many other learners share the table.
"""
import hashlib
import json
from collections.abc import Iterable

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore

from app import db
from app.embeddings import get_embeddings

DIMENSIONS = 1024


def _literal(vector: Iterable[float]) -> str:
    values = [float(x) for x in vector]
    if len(values) != DIMENSIONS:
        raise ValueError(f'Embedding size mismatch: this deployment stores {DIMENSIONS}-dimension vectors, '
                         f'the embedding model returned {len(values)}. Set EMBEDDING_DIMENSIONS={DIMENSIONS}.')
    return '[' + ','.join(repr(x) for x in values) + ']'


class PgVectorStore(VectorStore):
    def __init__(self, workspace: str, collection: str, embeddings: Embeddings):
        self.workspace, self.collection, self._embeddings = workspace, collection, embeddings

    @property
    def embeddings(self) -> Embeddings:
        return self._embeddings

    @classmethod
    def from_texts(cls, *args, **kwargs):          # required by the base class; the app never builds stores this way
        raise NotImplementedError('Use PgVectorStore(workspace, collection, embeddings)')

    # -- writes -----------------------------------------------------------------------
    def upsert(self, ids: list[str], vectors: list[list[float]], metadatas: list[dict], documents: list[str]) -> None:
        literals = [_literal(v) for v in vectors]          # validate every vector before writing anything
        with db.transaction() as conn:
            for chunk_id, literal, meta, text in zip(ids, literals, metadatas, documents):
                conn.execute(
                    'INSERT INTO app.chunks (workspace, collection, id, source, page, content, metadata, embedding) '
                    'VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector) '
                    'ON CONFLICT (workspace, collection, id) DO UPDATE SET source = EXCLUDED.source, page = EXCLUDED.page, '
                    'content = EXCLUDED.content, metadata = EXCLUDED.metadata, embedding = EXCLUDED.embedding',
                    (self.workspace, self.collection, chunk_id, str(meta.get('source', '')), meta.get('page') if isinstance(meta.get('page'), int) else None,
                     text, json.dumps(meta), literal))

    def add_documents(self, documents: list[Document], ids: list[str] | None = None, **kwargs) -> list[str]:
        ids = ids or [d.metadata.get('id') or hashlib.md5(d.page_content.encode()).hexdigest() for d in documents]
        vectors = self._embeddings.embed_documents([d.page_content for d in documents])
        self.upsert(ids, vectors, [d.metadata for d in documents], [d.page_content for d in documents])
        return ids

    def add_texts(self, texts, metadatas=None, ids=None, **kwargs) -> list[str]:
        metadatas = metadatas or [{} for _ in texts]
        return self.add_documents([Document(page_content=t, metadata=m) for t, m in zip(texts, metadatas)], ids=ids)

    def clear(self) -> None:
        with db.transaction() as conn:
            conn.execute('DELETE FROM app.chunks WHERE workspace = %s AND collection = %s', (self.workspace, self.collection))

    # -- reads ------------------------------------------------------------------------
    def existing_ids(self, ids: list[str]) -> set[str]:
        with db.transaction() as conn:
            rows = conn.execute('SELECT id FROM app.chunks WHERE workspace = %s AND collection = %s AND id = ANY(%s)',
                                (self.workspace, self.collection, ids)).fetchall()
        return {r['id'] for r in rows}

    def count(self) -> int:
        with db.transaction() as conn:
            return conn.execute('SELECT count(*) AS n FROM app.chunks WHERE workspace = %s AND collection = %s',
                                (self.workspace, self.collection)).fetchone()['n']

    def sources(self) -> list[dict]:
        with db.transaction() as conn:
            rows = conn.execute("SELECT source, count(*) AS chunks, coalesce(max(metadata->>'type'), 'pdf') AS type FROM app.chunks "
                                'WHERE workspace = %s AND collection = %s GROUP BY source', (self.workspace, self.collection)).fetchall()
        return sorted(({'source': r['source'] or 'unknown', 'chunks': r['chunks'], 'type': r['type']} for r in rows),
                      key=lambda x: x['source'].lower())

    def similarity_search(self, query: str, k: int = 4, **kwargs) -> list[Document]:
        literal = _literal(self._embeddings.embed_query(query))
        with db.transaction() as conn:
            conn.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")
            rows = conn.execute('SELECT content, metadata FROM app.chunks WHERE workspace = %s AND collection = %s '
                                'ORDER BY embedding <=> %s::vector LIMIT %s', (self.workspace, self.collection, literal, k)).fetchall()
        return [Document(page_content=r['content'], metadata=r['metadata']) for r in rows]


def for_current_workspace() -> PgVectorStore:
    from app.embeddings import collection_name
    from app.workspace import workspace_id
    return PgVectorStore(workspace_id.get(), collection_name(), get_embeddings())
