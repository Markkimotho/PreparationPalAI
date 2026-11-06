import json
from unittest.mock import patch

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app.quiz_agent import _final_answer, search_and_add_to_kb
from app.retriever import relevant_documents
from app.safety import SafetyError, moderate
from app.workspace import role


def test_physics_does_not_retrieve_bible():
    bible = Document(page_content='The Spirit searches all things, even the deep things of God.')
    physics = Document(page_content='Newton’s second law relates net force and acceleration: F = ma.')
    assert relevant_documents('Newton’s second law, force diagrams, and units', [bible, physics]) == [physics]


@pytest.mark.parametrize('permission,user_role', [(False, 'admin'), (True, 'reader')])
def test_web_requires_permission_and_editor(permission, user_role):
    token = role.set(user_role)
    try:
        with patch('app.quiz_agent.search_and_scrape') as search:
            result = search_and_add_to_kb.invoke({'topic': 'physics'},
                config={'configurable': {'allow_web': permission}})
            assert 'disabled' in result
            search.assert_not_called()
    finally:
        role.reset(token)


def test_failed_quiz_cannot_be_replaced_by_invented_final_answer():
    messages = [HumanMessage(content='quiz me on physics'),
                ToolMessage(content='Could not generate questions', name='make_quiz', tool_call_id='1'),
                AIMessage(content='Here are invented questions about the Bible')]
    answer = _final_answer(messages)
    assert 'could not create a grounded quiz' in answer
    assert 'Bible' not in answer


def test_quiz_display_hides_answer_and_raw_json():
    item = dict(type='mcq', question='What is force?', options=dict(A='ma', B='m/a', C='a/m', D='m+a'),
                correct='A', explanation='SECRET REFERENCE', source='mechanics.pdf')
    answer = _final_answer([HumanMessage(content='quiz'), ToolMessage(content=json.dumps([item]),
                           name='make_quiz', tool_call_id='1'), AIMessage(content='RAW DRAFT')])
    assert '**A.** ma' in answer
    assert all(s not in answer for s in ('SECRET', 'RAW', '"correct"'))


@pytest.mark.parametrize('raw', ['{"safe": false}', '{"safe": "true"}', '{}', 'invalid'])
def test_moderation_fails_closed(raw):
    with patch('langchain_ollama.ChatOllama.invoke', return_value=AIMessage(content=raw)):
        with pytest.raises(SafetyError):
            moderate('some user content', model='test', base_url='http://localhost:1')


def test_unsafe_generated_output_never_streams():
    from app.llm import ChatOllama
    raw = ChatResult(generations=[ChatGeneration(message=AIMessage(content='unsafe payload'))])
    def inspect(text, **kwargs):
        if 'unsafe payload' in text:
            raise SafetyError('blocked')
    with patch('app.llm.moderate', side_effect=inspect), \
         patch('langchain_ollama.ChatOllama._generate', return_value=raw):
        iterator = ChatOllama(model='test').stream([HumanMessage(content='safe input')])
        with pytest.raises(SafetyError):
            next(iterator)


def test_profanity_backstop_does_not_block_scientific_terms():
    from app.safety import check_language
    check_language('Discuss the classic classification of chemical substances and reproductive anatomy.')
    with pytest.raises(SafetyError):
        check_language('ＦＵＣＫ this')


@pytest.mark.asyncio
async def test_async_output_is_checked_before_first_chunk():
    from app.llm import ChatOllama
    raw = ChatResult(generations=[ChatGeneration(message=AIMessage(content='unsafe payload'))])
    with patch('app.llm.moderate', side_effect=[None, SafetyError('blocked')]), \
         patch('langchain_ollama.ChatOllama._generate', return_value=raw):
        with pytest.raises(SafetyError):
            await anext(ChatOllama(model='test').astream([HumanMessage(content='safe input')]))


def test_safety_failures_do_not_retry_or_become_empty_quizzes():
    from app.quiz import generate_questions
    retriever = patch('app.quiz.get_retriever')
    with retriever as get_retriever, patch('app.quiz._get_llm') as get_llm:
        get_retriever.return_value.invoke.return_value = [Document(page_content='Newton: F = ma.', metadata={'source': 'physics.pdf'})]
        get_llm.return_value.invoke.side_effect = SafetyError('blocked')
        with pytest.raises(SafetyError):
            generate_questions('Newton')
        assert get_llm.return_value.invoke.call_count == 1


def test_sse_safety_message_is_actionable_without_output_leak():
    from app.api import app
    from fastapi.testclient import TestClient
    def blocked(*args, **kwargs):
        raise SafetyError('Safety checking is unavailable. Please retry.')
        yield  # generator boundary
    with patch('app.api.require_model', return_value='test'), patch('app.api.lcel_chain.stream', side_effect=blocked):
        response = TestClient(app).post('/api/chat/stream', json={'question': 'Explain force.'})
    assert 'Safety checking is unavailable' in response.text
    assert '"type": "token"' not in response.text
    assert '"type": "done"' in response.text
