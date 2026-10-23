import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from app.flashcards import generate_cards
from app.quiz import generate_questions


def response(items, key):
    return SimpleNamespace(content=json.dumps({key: items}), response_metadata={})


def question(index, source='notes.pdf'):
    return dict(type='mcq', question=f'Question {index}?', source=source,
                options=dict(A='First', B='Second', C='Third', D='Fourth'), correct='A', explanation='Supported explanation.')


def test_quiz_generation_validates_multiple_small_batches():
    llm = Mock()
    llm.invoke.side_effect = [response([question(1), question(2)], 'questions'), response([question(3)], 'questions')]
    with patch('app.quiz._get_llm', return_value=llm), patch('app.quiz.get_retriever') as retriever:
        retriever.return_value.invoke.return_value = [Document(page_content='Evidence', metadata={'source': 'notes.pdf'})]
        items = generate_questions('topic', n=3)
    assert len(items) == 3
    assert llm.invoke.call_count == 2
    assert llm.invoke.call_args_list[0].kwargs['format']['properties']['questions']['maxItems'] == 2
    assert llm.invoke.call_args_list[1].kwargs['format']['properties']['questions']['maxItems'] == 1
    assert llm.invoke.call_args.kwargs['format']['$defs']['QuizItem']['properties']['source']['enum'] == ['notes.pdf']


def test_quiz_rejects_invented_sources_after_bounded_retry():
    llm = Mock()
    llm.invoke.return_value = response([question(1, 'invented.pdf')], 'questions')
    with patch('app.quiz._get_llm', return_value=llm), patch('app.quiz.get_retriever') as retriever:
        retriever.return_value.invoke.return_value = [Document(page_content='Evidence', metadata={'source': 'notes.pdf'})]
        assert generate_questions('topic', n=1) == []
    assert llm.invoke.call_count == 2


def test_cards_retry_duplicates_and_keep_requested_count():
    llm = Mock()
    llm.invoke.side_effect = [response([dict(front='Q1', back='A1'), dict(front='Q2', back='A2')], 'cards'),
                              response([dict(front='Q1', back='Repeated')], 'cards'),
                              response([dict(front='Q3', back='A3')], 'cards')]
    with patch('app.flashcards.ChatOllama', return_value=llm), patch('app.flashcards.get_retriever') as retriever:
        retriever.return_value.invoke.return_value = [Document(page_content='Evidence', metadata={'source': 'notes.pdf'})]
        items = generate_cards('topic', n=3)
    assert [card['front'] for card in items] == ['Q1', 'Q2', 'Q3']
    assert llm.invoke.call_count == 3


def test_truncated_response_is_not_accepted_as_a_partial_card():
    llm = Mock()
    llm.invoke.return_value = SimpleNamespace(content='{"cards":[{"front":"Q"', response_metadata={'done_reason': 'length'})
    with patch('app.flashcards.ChatOllama', return_value=llm), patch('app.flashcards.get_retriever') as retriever:
        retriever.return_value.invoke.return_value = [Document(page_content='Evidence')]
        assert generate_cards('topic', n=3) == []
    assert llm.invoke.call_count == 2
