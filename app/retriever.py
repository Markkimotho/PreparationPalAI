from langchain_core.vectorstores import VectorStoreRetriever

from app.config import get_settings
from app.vectorstore import get_vectorstore
from app.diagnostics import RETRIEVAL_FAILURES


def get_retriever(top_k: int | None = None) -> VectorStoreRetriever:
    settings = get_settings()
    k = top_k if top_k is not None else settings.top_k
    try:
        return get_vectorstore().as_retriever(search_type="similarity", search_kwargs={"k": k})
    except Exception:
        RETRIEVAL_FAILURES.inc()
        raise
