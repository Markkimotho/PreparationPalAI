"""Versioned offline contract gate and optional real-Ollama quality benchmark."""
import argparse
import json
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from langchain_core.documents import Document
from app.config import get_settings

DATASET = Path(__file__).resolve().parents[1] / 'evals/golden.json'


def evidence(case, answer, sources):
    lower = answer.lower()
    return dict(citation=case['source'] in sources and case['source'] in answer,
                grounded=all(term.lower() in lower for term in case['terms']) and
                         not any(term.lower() in lower for term in case['forbidden']))


def run(live=False, model=None):
    data = json.loads(DATASET.read_text())
    docs = [Document(page_content=d['text'], metadata=dict(source=d['source'], page=d['page']))
            for d in data['documents']]
    for case in data['cases']:
        assert case['source'] in {d.metadata['source'] for d in docs}
        assert case['terms']
    report = dict(dataset_version=data['version'], mode='live' if live else 'offline-contract',
                  model=model, embedding_model=get_settings().ollama_embedding_model, cases=[])
    if not live:
        report.update(passed=True, checks=len(data['cases']),
                      note='Dataset/schema gate only. Model quality has NOT been measured.')
        return report
    import httpx
    from app.embeddings import get_embeddings
    from app.llm import ChatOllama
    from app.prompts import QA_PROMPT
    from app.quiz import generate_questions
    from app.flashcards import generate_cards
    from langchain_chroma import Chroma
    settings = get_settings()
    model = model or settings.ollama_model
    tags = httpx.get(f'{settings.ollama_base_url}/api/tags', timeout=5).json()['models']
    selected = next((t for t in tags if t['name'] == model), None)
    if not selected:
        raise RuntimeError('Requested evaluation model is not installed')
    report.update(model=model, model_digest=selected.get('digest'),
                  ollama_version=httpx.get(f'{settings.ollama_base_url}/api/version', timeout=5).json())
    with tempfile.TemporaryDirectory(prefix='preppal-eval-') as temp:
        store = Chroma(collection_name='quality-golden', persist_directory=temp, embedding_function=get_embeddings())
        store.add_documents(docs)
        retriever = store.as_retriever(search_kwargs={'k': 2})
        llm = ChatOllama(model=model, base_url=settings.ollama_base_url, temperature=0)
        for case in data['cases']:
            retrieved = retriever.invoke(case['question'])
            sources = [d.metadata['source'] for d in retrieved]
            context = '\n\n'.join(f"[Source: {d.metadata['source']}, page {d.metadata['page']}] {d.page_content}" for d in retrieved)
            answer = llm.invoke(QA_PROMPT.invoke(dict(context=context, chat_history=[], input=case['question']))).content
            result = dict(id=case['id'], retrieval=case['source'] in sources, **evidence(case, answer, sources))
            report['cases'].append(result)
        with patch('app.quiz.get_retriever', return_value=retriever), patch('app.flashcards.get_retriever', return_value=retriever):
            questions = generate_questions('binary search', n=3, model=model)
            cards = generate_cards('binary search', n=3, model=model)
        report['quiz_validity'] = sum(bool(q.get('question') and q.get('correct') in q.get('options', {}) and len(q.get('options', {})) == 4) for q in questions) / 3
        report['flashcard_validity'] = sum(bool(c.get('front') and len(c.get('back', '')) >= 10) for c in cards) / 3
    report['metrics'] = {key: sum(c[key] for c in report['cases']) / len(report['cases']) for key in ('retrieval', 'citation', 'grounded')}
    report['passed'] = (all(v >= .75 for v in report['metrics'].values()) and
                        report['quiz_validity'] >= .66 and report['flashcard_validity'] >= .66)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--model')
    parser.add_argument('--report', default='quality-report.json')
    args = parser.parse_args()
    try:
        report = run(args.live, args.model)
    except Exception as exc:
        report = dict(passed=False, mode='live' if args.live else 'offline-contract', error_type=type(exc).__name__)
    Path(args.report).write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
