"""Quiz generation, answer validation, and concept explanation from the knowledge base."""

import json
import logging
import re
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal
from app.generation import validated_batches
from app.safety import SafetyError, check_language

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from app.llm import ChatOllama

from app.config import get_settings
from app.retriever import get_retriever
from app.prompt_library import PromptProfile, render_prompt

logger = logging.getLogger(__name__)


class Rubric(BaseModel):
    reasoning: int = Field(ge=0, le=40)
    accuracy: int = Field(ge=0, le=40)
    clarity: int = Field(ge=0, le=20)


class WrittenEvaluation(BaseModel):
    score: int = Field(ge=0, le=100)
    feedback: str = Field(min_length=1)
    key_missed: list[str] = []
    hint: str = ''
    rubric: Rubric | None = None


class QuizItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    type: Literal['mcq', 'true_false', 'short_answer']
    question: str = Field(min_length=1)
    drawing_required: bool = False
    drawing_prompt: str = Field(default='', max_length=1000)
    source: str = Field(min_length=1)
    difficulty: str = 'medium'
    correct: str | bool | None = None
    options: dict[str, str] = Field(default_factory=dict)
    explanation: str = ''
    sample_answer: str = ''
    key_concepts: list[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid_answer(self):
        if self.drawing_required and self.type != 'short_answer':
            raise ValueError('Drawing tasks require a written-answer question')
        if self.type == 'mcq' and (set(self.options) != set('ABCD') or self.correct not in self.options):
            raise ValueError('MCQ needs four options and one matching answer')
        if self.type == 'mcq' and any(not text for text in self.options.values()):
            raise ValueError('Empty option')
        if self.type in ('mcq', 'true_false') and not self.explanation:
            raise ValueError('An explanation is required')
        if self.type == 'true_false' and not isinstance(self.correct, bool):
            raise ValueError('True/false needs a boolean answer')
        if self.type == 'short_answer' and not self.sample_answer.strip():
            raise ValueError('Short answer needs a reference')
        return self


class QuizBatch(BaseModel):
    questions: list[QuizItem] = Field(max_length=2)

# ── Prompts ───────────────────────────────────────────────────────────────────


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_json(text: str) -> Any:
    """Robustly extract JSON from an LLM response that may contain extra text."""
    text = re.sub(r'<think>[\s\S]*?</think>', '', text).strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r"\[[\s\S]*\]", r"\{[\s\S]*\}"]:
        match = re.search(pattern, text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                continue
    raise ValueError('The model returned incomplete or invalid JSON.')


def _build_context(docs: list[Document]) -> str:
    return "\n\n---\n\n".join(
        f"[Source: {doc.metadata.get('source', 'unknown')}, "
        f"Page {doc.metadata.get('page', '?')}]\n{doc.page_content}"
        for doc in docs
    )


def _get_llm(model: str | None = None, temperature: float = 0.3, response_format=None) -> ChatOllama:
    settings = get_settings()
    return ChatOllama(
        model=model or settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=temperature,
        keep_alive=settings.ollama_keep_alive,
        **({'format': response_format} if response_format else {}),
    )


# ── Public API ────────────────────────────────────────────────────────────────


def generate_questions(
    topic: str,
    question_type: str = "mcq",
    n: int = 5,
    difficulty: str = "medium",
    exam_type: str = "general exam",
    model: str | None = None,
    top_k: int = 8,
    profile: PromptProfile | None = None,
) -> list[dict]:
    """Generate quiz questions from the knowledge base on a given topic.

    question_type: "mcq" | "true_false" | "short_answer" | "mixed"
    Returns a list of question dicts (at most n).
    Returns [] when the knowledge base has no relevant content.
    """
    retriever = get_retriever(top_k=top_k)
    docs = retriever.invoke(topic)
    if not docs:
        logger.warning('No relevant documents found for quiz generation')
        return []

    context = _build_context(docs)
    schema = QuizBatch.model_json_schema()
    if question_type != 'mixed':
        item_schema = schema['$defs']['QuizItem']
        props = item_schema['properties']
        props['type']['enum'] = [question_type]
        if question_type == 'mcq':
            props['correct'] = dict(type='string', enum=list('ABCD'))
            props['options'] = dict(type='object', properties={key: {'type': 'string', 'minLength': 1} for key in 'ABCD'},
                                   required=list('ABCD'), additionalProperties=False)
            item_schema['required'] += ['correct', 'options', 'explanation']
            for key in ('sample_answer', 'key_concepts'):
                props.pop(key)
        elif question_type == 'true_false':
            props['correct'] = dict(type='boolean')
            item_schema['required'] += ['correct', 'explanation']
        else:
            item_schema['required'] += ['sample_answer']
    sources = {str(doc.metadata.get('source', 'unknown')) for doc in docs}
    schema['$defs']['QuizItem']['properties']['source']['enum'] = sorted(sources)
    def validate(item):
        if item['source'] not in sources:
            raise ValueError('Unknown source')
        if question_type != 'mixed' and item['type'] != question_type:
            raise ValueError('Wrong question format')
    def prompt(count, existing, repair, batch_schema, feedback):
        return render_prompt('quiz_questions', profile=profile, count=count, topic=topic,
            question_type=question_type, difficulty=difficulty, exam_context=exam_type,
            evidence_mode='documents', context=context, schema=batch_schema, repair=repair,
            source_labels=sorted(sources),
            validation_feedback=feedback,
            already_covered=[q['question'] for q in existing])
    llm = _get_llm(model, temperature=0.2, response_format=schema)
    try:
        return validated_batches(llm, prompt, _extract_json, QuizBatch, n, 'questions', 'question', validate, schema=schema)
    except SafetyError:
        raise
    except Exception as exc:
        logger.warning('Quiz generation failed', extra={'error_type': type(exc).__name__})
        return []


def validate_answer(
    question: str,
    correct_answer: Any,
    student_answer: str,
    question_type: str = "short_answer",
    model: str | None = None,
    context_docs: list[Document] | None = None,
    profile: PromptProfile | None = None,
    evidence_context: str = '',
) -> dict:
    """Grade a student answer.

    Returns: {"score": 0-100, "is_correct": bool, "feedback": str, "key_missed": list, "hint": str}
    MCQ and True/False are graded deterministically; short answer uses the LLM.
    """
    for text in (question, str(correct_answer), student_answer):
        check_language(text)
    if question_type in ("mcq", "true_false"):
        expected = str(correct_answer).strip().upper()
        given = student_answer.strip().upper()
        is_correct = expected == given
        return {
            "score": 100 if is_correct else 0,
            "is_correct": is_correct,
            "feedback": "Correct!" if is_correct else f"Incorrect. The correct answer is: {correct_answer}",
            "key_missed": [] if is_correct else [str(correct_answer)],
            "hint": "",
        }

    context = _build_context(context_docs[:3]) if context_docs else evidence_context
    llm = _get_llm(model, temperature=0, response_format=WrittenEvaluation.model_json_schema())
    prompt = render_prompt('grade_answer', profile=profile,
        question=question,
        reference=str(correct_answer)[:8000],
        student_answer=student_answer,
        context=context[:12000],
        evidence_mode='documents' if context else 'reference',
        schema=WrittenEvaluation.model_json_schema(),
    )
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        result = WrittenEvaluation.model_validate(_extract_json(response.content)).model_dump()
        if result['rubric'] is not None:
            result['score'] = sum(result['rubric'].values())
        result['is_correct'] = result['score'] >= 70
        return result
    except Exception as exc:
        if isinstance(exc, SafetyError):
            raise
        logger.warning('Answer evaluation failed', extra={'error_type': type(exc).__name__})
        return {
            "score": 0,
            "is_correct": False,
            "feedback": "Could not grade answer: the model returned no valid evaluation. Retry or choose another model.",
            "key_missed": [],
            "hint": "",
        }


def explain_concept(concept: str, model: str | None = None, top_k: int = 6, profile: PromptProfile | None = None) -> str:
    """Return a detailed explanation of a concept from the knowledge base."""
    check_language(concept)
    retriever = get_retriever(top_k=top_k)
    docs = retriever.invoke(concept)
    if not docs:
        return 'No relevant information was found in the knowledge base. Upload material covering this concept.'

    context = _build_context(docs)
    llm = _get_llm(model, temperature=0)
    prompt = render_prompt('explain', profile=profile, concept=concept, context=context, evidence_mode='documents')
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content
    except Exception as exc:
        if isinstance(exc, SafetyError):
            raise
        return f"Error generating explanation: {exc}"
