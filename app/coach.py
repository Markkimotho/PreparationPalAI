"""Persistent local preparation sessions; answers and timers are server-owned."""
import json
import sqlite3
import time
import uuid
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field, model_validator

from app.config import get_settings
from app.model_catalog import require_model
from app.quiz import _build_context, _extract_json, _get_llm, validate_answer
from app.retriever import get_retriever
from app.prompt_library import PROMPT_VERSION, PromptProfile, render_prompt
from app.generation import validation_feedback
from app.safety import SafetyError

router = APIRouter(prefix='/api/coach', tags=['Preparation coach'])


class Start(BaseModel):
    profile: PromptProfile = Field(default_factory=PromptProfile)
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
    drawing_required: bool = False
    drawing_prompt: str = Field(default='', max_length=1000)
    topic: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    options: dict[str, str] = {}
    explanation: str = ''

    @model_validator(mode='after')
    def validate_answer_shape(self):
        if self.drawing_required and self.type in ('mcq', 'true_false'):
            raise ValueError('Drawing tasks require a written-answer question')
        if self.type == 'mcq' and (set(self.options) != set('ABCD') or self.answer not in self.options):
            raise ValueError('MCQ requires four options and a matching answer')
        if self.type == 'true_false' and self.answer.lower() not in ('true', 'false'):
            raise ValueError('True/false reference must be True or False')
        return self


class Answer(BaseModel):
    learner: str = Field(min_length=1, max_length=100)
    answer: str = Field(max_length=20000)
    confidence: int = Field(default=3, ge=1, le=5)
    index: int = Field(ge=0)


class QuestionBatch(BaseModel):
    questions: list[Question] = Field(min_length=1, max_length=2)


def generate_questions(req: Start, model: str, context: str, focus: str) -> list[dict]:
    """Keep each response within the configured output budget, never accept partial JSON."""
    questions = []
    schema = QuestionBatch.model_json_schema()
    required_type = 'free_response' if req.mode == 'interview' else req.question_type
    if required_type != 'mixed':
        properties = schema['$defs']['Question']['properties']
        properties['type']['enum'] = [required_type]
        if required_type == 'mcq':
            properties['answer']['enum'] = list('ABCD')
            properties['options'] = dict(type='object', properties={key: {'type': 'string'} for key in 'ABCD'},
                                         required=list('ABCD'), additionalProperties=False)
    llm = _get_llm(model, response_format=schema)
    while len(questions) < req.n:
        count = min(2, req.n - len(questions))
        batch_schema = deepcopy(schema)
        batch_schema['properties']['questions'].update(minItems=count, maxItems=count)
        feedback = None
        for attempt in range(2):
            try:
                prompt = render_prompt('coach_questions', profile=req.profile, topic=focus,
                    mode=req.mode, difficulty=req.difficulty, question_type=required_type,
                    count=count, context=context, schema=batch_schema, repair=bool(attempt),
                    validation_feedback=feedback,
                    evidence_mode='documents' if context else 'general',
                    already_covered=[q['question'] for q in questions],
                    preferred_types=['mcq', 'short_answer'] if req.mode == 'exam' and required_type == 'mixed' and count == 2 else [])
                response = llm.invoke([HumanMessage(content=prompt)], format=batch_schema)
                if getattr(response, 'response_metadata', {}).get('done_reason') == 'length':
                    raise ValueError('Output limit reached')
                raw = _extract_json(response.content)
                # Some older local runners ignore the wrapper schema but emit a valid array.
                batch = QuestionBatch.model_validate({'questions': raw} if isinstance(raw, list) else raw)
                if len(batch.questions) != count:
                    raise ValueError('Wrong question count')
                existing = {q['question'].strip().casefold() for q in questions}
                for q in batch.questions:
                    if q.question.strip().casefold() in existing:
                        raise ValueError('Repeated question')
                    existing.add(q.question.strip().casefold())
                    if req.mode == 'interview' and q.type != 'free_response':
                        raise ValueError('Interview requires written questions')
                    if req.mode != 'interview' and req.question_type != 'mixed' and q.type != req.question_type:
                        raise ValueError('Wrong question format')
                questions.extend(q.model_dump() for q in batch.questions)
                break
            except (ValueError, TypeError) as exc:
                feedback = validation_feedback(exc)
                if attempt:
                    raise
    return questions


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
    context = _build_context(docs)[:12000]
    grounding = 'documents' if docs else 'model-general knowledge'
    try:
        questions = generate_questions(req, model, context, focus)
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
        if isinstance(exc, SafetyError):
            raise
        raise HTTPException(502, 'The model could not finish a valid question set. Try fewer questions or choose another installed model. Your topic and settings have been kept.') from exc
    now = time.time()
    session = dict(id=uuid.uuid4().hex, learner=req.learner, topic=focus, mode=req.mode,
                   profile=req.profile.model_dump(), prompt_version=PROMPT_VERSION,
                   model=model, questions=questions, answers=[], started=now, last_answer=now,
                   deadline=now + req.minutes * 60 if req.mode == 'exam' and req.minutes else 0,
                   context=context, grounding=grounding, sources=[dict(source=d.metadata.get('source', 'unknown'),
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
    # Read before inference; acquire the write lock only when committing the answer.
    with connect() as db:
        session = load(db, session_id, req.learner)
    if public(session)['done']:
        raise HTTPException(409, 'Session has finished. Open the results.')
    index = len(session['answers'])
    if req.index != index:
        raise HTTPException(409, 'Question already submitted; refresh the session.')
    q = session['questions'][index]
    submitted_at = time.time()
    require_model(session['model'])
    profile = PromptProfile.model_validate(session.get('profile', {}))
    result = validate_answer(q['question'], q['answer'], req.answer, q['type'], session['model'],
                             profile=profile, evidence_context=session.get('context', ''))
    if result['feedback'].startswith('Could not grade answer:'):
        raise HTTPException(502, 'Grading failed; your answer has not been recorded. Retry.')
    result['score'] = max(0, min(100, int(result['score'])))
    result['hint'] = result.get('hint') or f"Compare your reasoning with: {q['explanation'] or q['answer']}"
    session['answers'].append(dict(question=q['question'], topic=q['topic'],
        answer=req.answer, confidence=req.confidence, seconds=round(submitted_at - session['last_answer']),
        question_type=q['type'], grounding=session['grounding'],
        result=result, reference=q['answer'], explanation=q['explanation']))
    if session['mode'] == 'interview' and not session['followed_up']:
        prompt = render_prompt('interview_followup', profile=profile, question=q['question'],
            student_answer=req.answer, feedback=result['feedback'], context=session.get('context', ''),
            evidence_mode='documents' if session.get('context') else 'general', schema=Question.model_json_schema())
        try:
            follow = Question.model_validate(_extract_json(
                _get_llm(session['model'], response_format=Question.model_json_schema()).invoke([HumanMessage(content=prompt)]).content))
            if follow.type != 'free_response':
                raise ValueError('Interview follow-up must be written')
            session['questions'].insert(index + 1, follow.model_dump())
            session['followed_up'] = True
        except Exception:
            pass
    if session['mode'] in ('recap', 'review') and result['score'] < 70 and index + 1 < len(session['questions']):
        expected_type = session['questions'][index + 1]['type']
        prompt = render_prompt('adaptive_question', profile=profile, topic=q['topic'],
            misconceptions=result.get('key_missed', []), feedback=result['feedback'], confidence=req.confidence,
            expected_type=expected_type, context=session.get('context', ''),
            evidence_mode='documents' if session.get('context') else 'general', schema=Question.model_json_schema())
        try:
            adapted = Question.model_validate(_extract_json(
                _get_llm(session['model'], response_format=Question.model_json_schema()).invoke([HumanMessage(content=prompt)]).content))
            if adapted.type == expected_type:
                session['questions'][index + 1] = {**adapted.model_dump(), 'adaptive': True}
        except Exception:
            pass
    session['last_answer'] = time.time()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        latest = load(db, session_id, req.learner)
        if len(latest['answers']) != index:
            raise HTTPException(409, 'Answer already recorded; refresh this session.')
        save(db, session)
    return public(session)
