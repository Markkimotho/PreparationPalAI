"""Persistent local preparation sessions; answers and timers are server-owned."""
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.config import get_settings
from app.model_catalog import require_model
from app.quiz import _build_context, _extract_json, _get_llm, validate_answer
from app.retriever import get_retriever

router = APIRouter(prefix='/api/coach', tags=['Preparation coach'])


class Start(BaseModel):
    learner: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=500)
    mode: Literal['recap', 'exam', 'interview', 'review'] = 'recap'
    difficulty: Literal['easy', 'medium', 'hard', 'mixed'] = 'medium'
    n: int = Field(default=5, ge=2, le=20)
    minutes: int = Field(default=0, ge=0, le=180)
    model: str | None = None
    question_type: Literal['mixed', 'mcq', 'true_false', 'short_answer', 'free_response'] = 'mixed'


class Question(BaseModel):
    type: Literal['mcq', 'true_false', 'short_answer', 'free_response']
    question: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    options: dict[str, str] = {}
    explanation: str = ''


class Answer(BaseModel):
    learner: str = Field(min_length=1, max_length=100)
    answer: str = Field(max_length=20000)
    confidence: int = Field(default=3, ge=1, le=5)
    index: int = Field(ge=0)


@contextmanager
def connect():
    path = Path(get_settings().coach_db)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, learner TEXT, body TEXT)')
    try:
        with db:
            yield db
    finally:
        db.close()


def load(db, session_id: str, learner: str) -> dict:
    row = db.execute('SELECT body FROM sessions WHERE id=? AND learner=?',
                     (session_id, learner)).fetchone()
    if not row:
        raise HTTPException(404, 'Session not found')
    return json.loads(row[0])


def save(db, session: dict):
    db.execute('INSERT OR REPLACE INTO sessions VALUES (?, ?, ?)',
               (session['id'], session['learner'], json.dumps(session)))


def summary(session: dict) -> dict:
    topics = {}
    for answer in session['answers']:
        entry = topics.setdefault(answer['topic'], {'attempts': 0, 'score': 0, 'missed': []})
        entry['attempts'] += 1
        entry['score'] += answer['result']['score']
        entry['missed'].extend(answer['result'].get('key_missed', []))
    breakdown = [dict(topic=topic, attempts=e['attempts'],
                      score=round(e['score'] / e['attempts']),
                      missed=list(dict.fromkeys(e['missed']))) for topic, e in topics.items()]
    weak = sorted([e for e in breakdown if e['score'] < 70], key=lambda e: e['score'])
    return dict(score=round(sum(a['result']['score'] for a in session['answers']) /
                            max(1, len(session['questions']))), topics=breakdown, weak=weak,
                next_actions=[f"Review {e['topic']}, explain the missed concepts, then practise again."
                              for e in weak] or ['Revisit this topic at a higher difficulty.'])


def public(session: dict) -> dict:
    index = len(session['answers'])
    done = index >= len(session['questions']) or bool(
        session['deadline'] and time.time() >= session['deadline'])
    question = None
    if not done:
        question = {k: v for k, v in session['questions'][index].items()
                    if k not in ('answer', 'explanation')}
    return dict(id=session['id'], topic=session['topic'], mode=session['mode'],
                model=session['model'], index=index, total=len(session['questions']),
                deadline=session['deadline'], question=question, done=done,
                grounding=session['grounding'], sources=session['sources'],
                answers=session['answers'], summary=summary(session) if done else None)


def weak_topics(db, learner: str) -> list[str]:
    totals = {}
    for (body,) in db.execute('SELECT body FROM sessions WHERE learner=?', (learner,)):
        for a in json.loads(body)['answers']:
            scores = totals.setdefault(a['topic'], [])
            scores.append(a['result']['score'])
    return sorted((t for t, scores in totals.items() if sum(scores) / len(scores) < 70),
                  key=lambda t: sum(totals[t]) / len(totals[t]))[:5]


@router.get('/history')
def history(learner: str):
    with connect() as db:
        sessions = [json.loads(row[0]) for row in db.execute(
            'SELECT body FROM sessions WHERE learner=? ORDER BY rowid DESC LIMIT 30', (learner,))]
        return dict(sessions=[dict(id=s['id'], topic=s['topic'], mode=s['mode'],
                                   completed=public(s)['done']) for s in sessions],
                    weak_topics=weak_topics(db, learner))


@router.post('/sessions')
def start(req: Start):
    model = require_model(req.model)
    with connect() as db:
        weak = weak_topics(db, req.learner) if req.mode == 'review' else []
    focus = ', '.join(weak) if weak else req.topic.strip()
    try:
        docs = get_retriever(top_k=8).invoke(focus)
    except Exception:
        docs = []
    context = _build_context(docs)[:24000]
    grounding = 'documents' if docs else 'model-general knowledge'
    prompt = f'''Create {req.n} {req.difficulty} questions about {focus} for {req.mode}.
Cover sciences, mathematics, engineering or other fields as requested.
For recap: progress from definitions to application. For interview: probe reasoning,
tradeoffs, assumptions and derivations. Include calculation, units, multi-step problems
and interpretation when appropriate. Exam MUST mix at least two formats.
Interview uses free_response. For other modes the requested format is {req.question_type}.
For mixed use at least two of mcq, true_false, short_answer or free_response.
Use only the context when present. Otherwise use general knowledge, acknowledge uncertainty,
and never invent sources. Include a precise reference answer and solution in explanation.
Return ONLY a JSON array. Each object has: type, question, topic (specific subtopic),
answer (A/B/C/D for mcq, True/False for true_false, reference answer otherwise),
options (A/B/C/D object for mcq, empty object otherwise), explanation.
Context: {context or 'No relevant documents: general knowledge.'}'''
    try:
        raw = _extract_json(_get_llm(model).invoke([HumanMessage(content=prompt)]).content)
        questions = [Question.model_validate(q).model_dump() for q in raw][:req.n]
        if len(questions) != req.n:
            raise ValueError(f'Expected {req.n} questions; received {len(questions)}')
        for q in questions:
            if q['type'] == 'mcq' and (set(q['options']) != set('ABCD') or q['answer'] not in q['options']):
                raise ValueError('Invalid MCQ options')
            if q['type'] == 'true_false' and q['answer'].lower() not in ('true', 'false'):
                raise ValueError('Invalid true/false answer')
        if req.mode == 'interview' and any(q['type'] != 'free_response' for q in questions):
            raise ValueError('Interview requires written reasoning questions; retry')
        if req.mode != 'interview' and req.question_type != 'mixed' and any(
                q['type'] != req.question_type for q in questions):
            raise ValueError('Model did not follow the requested question format; retry')
        if req.mode == 'exam' and req.question_type == 'mixed' and len({q['type'] for q in questions}) < 2:
            raise ValueError('Exam model output must include mixed formats; retry')
    except Exception as exc:
        raise HTTPException(502, f'Could not generate valid questions. Retry or choose another model: {exc}') from exc
    now = time.time()
    session = dict(id=uuid.uuid4().hex, learner=req.learner, topic=focus, mode=req.mode,
                   model=model, questions=questions, answers=[], started=now, last_answer=now,
                   deadline=now + req.minutes * 60 if req.mode == 'exam' and req.minutes else 0,
                   grounding=grounding, sources=[dict(source=d.metadata.get('source', 'unknown'),
                   page=d.metadata.get('page', '?')) for d in docs], followed_up=False)
    with connect() as db:
        save(db, session)
    return public(session)


@router.get('/sessions/{session_id}')
def get_session(session_id: str, learner: str):
    with connect() as db:
        return public(load(db, session_id, learner))


@router.post('/sessions/{session_id}/answers')
def answer(session_id: str, req: Answer):
    # A write transaction prevents concurrent submissions advancing the same question twice.
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        session = load(db, session_id, req.learner)
        if public(session)['done']:
            raise HTTPException(409, 'Session has finished. Open the results.')
        index = len(session['answers'])
        if req.index != index:
            raise HTTPException(409, 'Question already submitted; refresh the session.')
        q = session['questions'][index]
        submitted_at = time.time()
        require_model(session['model'])
        result = validate_answer(q['question'], q['answer'], req.answer,
                                 q['type'], session['model'])
        if result['feedback'].startswith('Could not grade answer:'):
            raise HTTPException(502, 'Grading failed; your answer has not been recorded. Retry.')
        result['score'] = max(0, min(100, int(result['score'])))
        result['hint'] = result.get('hint') or f"Compare your reasoning with: {q['explanation'] or q['answer']}"
        session['answers'].append(dict(question=q['question'], topic=q['topic'],
            answer=req.answer, confidence=req.confidence, seconds=round(submitted_at - session['last_answer']),
            result=result, reference=q['answer'], explanation=q['explanation']))
        if session['mode'] == 'interview' and not session['followed_up']:
            prompt = f'''Ask one technical follow-up probing a gap or extending the learner's reasoning.
Question: {q['question']}\nAnswer: {req.answer}\nFeedback: {result['feedback']}
Return JSON with type="free_response", question, topic, answer (reference), explanation, options={{}}.'''
            try:
                follow = Question.model_validate(_extract_json(
                    _get_llm(session['model']).invoke([HumanMessage(content=prompt)]).content))
                session['questions'].insert(index + 1, follow.model_dump())
                session['followed_up'] = True
            except Exception:
                # Save the evaluated answer even if optional follow-up generation fails.
                pass
        session['last_answer'] = time.time()
        save(db, session)
        return public(session)
