from langchain_core.vectorstores import VectorStoreRetriever

from app.config import get_settings
from app.vectorstore import get_vectorstore
from app.diagnostics import RETRIEVAL_FAILURES
import re
from langchain_core.runnables import RunnableLambda

_STOP = set('a an the is are was were of to for in on and or with from about me my what which how explain describe generate create make quiz questions question exam test practice main topics knowledge material please'.split())


def relevant_documents(query, docs):
    """Conservative lexical admission check, not a truth/citation verifier.

    Vector top-k always returns neighbours, even for an unrelated collection.
    Require at least one non-generic topic term in the passage itself. This can
    reject synonyms; prefer an honest missing-source result to unrelated study.
    """
    def words(text):
        return {w.rstrip('s') for w in re.findall(r'[^\W\d_]{3,}', text.casefold()) if w not in _STOP}
    terms = words(query)
    return [doc for doc in docs if terms and terms & words(doc.page_content)]


def get_retriever(top_k: int | None = None, *, inventory: bool = False):
    settings = get_settings()
    k = top_k if top_k is not None else settings.top_k
    try:
        retriever = get_vectorstore().as_retriever(search_type="similarity", search_kwargs={"k": k})
        if inventory:
            return retriever
        def retrieve(query):
            return relevant_documents(query, retriever.invoke(query))
        return RunnableLambda(retrieve)
    except Exception:
        RETRIEVAL_FAILURES.inc()
        raise
