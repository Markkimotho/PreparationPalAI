"""Offline study packs: real PDF form fields, no scripts or remote assets."""
import html
import json
from typing import Literal

import pymupdf as pdf
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.config import get_settings
from app.model_catalog import require_model
from app.safety import moderate

router = APIRouter(prefix='/api/exports', tags=['Study exports'])


class ExportQuestion(BaseModel):
    model_config = ConfigDict(extra='ignore', str_strip_whitespace=True)
    question: str = Field(min_length=1, max_length=4000)
    options: dict[str, str] = Field(default_factory=dict, max_length=6)
    type: str = Field(default='short_answer', max_length=30)
    answer: str | bool | None = None
    correct: str | bool | None = None
    sample_answer: str = Field(default='', max_length=6000)
    explanation: str = Field(default='', max_length=6000)
    source: str = Field(default='', max_length=500)

    @model_validator(mode='after')
    def bounded_options(self):
        if sum(len(k) + len(v) for k, v in self.options.items()) > 6000:
            raise ValueError('Question options are too long')
        if self.answer is not None and len(str(self.answer)) > 6000:
            raise ValueError('Answer is too long')
        return self


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(default='Study practice', min_length=1, max_length=160)
    kind: Literal['exam', 'worksheet', 'checklist', 'answers'] = 'exam'
    format: Literal['pdf', 'markdown'] = 'pdf'
    questions: list[ExportQuestion] = Field(default_factory=list, max_length=50)
    session_id: str | None = Field(default=None, max_length=100)
    learner: str = Field(default='', max_length=100)
    deck_id: str | None = Field(default=None, max_length=100)
    model: str | None = None


def _text(value):
    # Escape all text before HTML layout: no remote images, links or markup.
    return html.escape(str(value)).replace('\n', '<br>')


def _block(page, rect, text, size=12):
    spare, scale = page.insert_htmlbox(rect, f'<div>{text}</div>',
        css=f'* {{font-family: sans-serif; font-size: {size}pt; color: #202b35; line-height: 1.45}}',
        scale_low=0.8)
    if spare < 0:
        raise ValueError('This question is too long for a readable PDF page. Shorten it or export Markdown.')


def _field(page, name, rect, label, *, choices=None, checkbox=False):
    widget = pdf.Widget()
    widget.field_name = name
    widget.field_label = label
    widget.rect = pdf.Rect(rect)
    widget.field_type = pdf.PDF_WIDGET_TYPE_CHECKBOX if checkbox else (
        pdf.PDF_WIDGET_TYPE_COMBOBOX if choices else pdf.PDF_WIDGET_TYPE_TEXT)
    widget.field_value = 'Off' if checkbox else ''
    widget.border_color = (0.45, 0.52, 0.58)
    widget.border_width = 0.7
    widget.fill_color = (0.97, 0.98, 0.99)
    widget.text_fontsize = 11
    if choices:
        widget.choice_values = ['', *choices]
    elif not checkbox:
        widget.field_flags = pdf.PDF_TX_FIELD_IS_MULTILINE
    page.add_widget(widget)


def render_pdf(req: ExportRequest) -> bytes:
    with pdf.open() as document:
        for index, q in enumerate(req.questions):
            page = document.new_page(width=595, height=842)
            _block(page, (42, 30, 553, 72), _text(req.title), 20)
            _block(page, (42, 78, 553, 112),
                   f'{req.kind.title()} · {index + 1} / {len(req.questions)} · PreparationPalAI', 10)
            if index == 0 and req.kind != 'answers':
                _block(page, (42, 119, 88, 145), 'Name', 10)
                _field(page, 'learner_name', (90, 117, 355, 143), 'Your name')
                _block(page, (375, 119, 416, 145), 'Date', 10)
                _field(page, 'date', (418, 117, 553, 143), 'Date')
            body = f'<b>{index + 1}. {_text(q.question)}</b>'
            if req.kind == 'answers':
                reference = q.answer if q.answer is not None else q.correct
                if reference is None:
                    reference = q.sample_answer or 'No reference answer supplied.'
                body += f'<br><br><b>Reference answer:</b> {_text(reference)}<br>{_text(q.explanation)}'
            else:
                options = q.options or ({'True': 'True', 'False': 'False'} if q.type == 'true_false' else {})
                body += ''.join(f'<br><br><b>{_text(k)}.</b> {_text(v)}' for k, v in options.items())
            _block(page, (42, 165, 553, 552), body)
            if req.kind == 'checklist':
                _field(page, f'understood_{index}', (43, 578, 62, 597), f'Question {index+1}: I can explain this', checkbox=True)
                _block(page, (73, 576, 540, 606), 'I can explain this without notes', 11)
                _field(page, f'notes_{index}', (42, 627, 553, 743), f'Question {index+1}: revision notes')
            elif req.kind != 'answers':
                choices = list(q.options) if req.kind == 'exam' and q.options else (
                    ['True', 'False'] if req.kind == 'exam' and q.type == 'true_false' else None)
                _block(page, (42, 575, 553, 604), 'Your answer' if choices else 'Your answer and working', 11)
                _field(page, f'answer_{index}', (42, 610, 553, 645 if choices else 743), f'Answer to question {index+1}', choices=choices)
            _block(page, (42, 770, 553, 818),
                   'AI study material · Check references before formal assessment. '
                   'Fill in a PDF reader and save a copy, or print and write by hand.', 9)
        document.set_metadata({'title': req.title, 'author': 'PreparationPalAI', 'subject': req.kind})
        return document.tobytes(garbage=4, deflate=True)


def render_markdown(req):
    lines = [f'# {req.title}', '', 'AI study material. Check references before formal assessment.', '']
    for i, q in enumerate(req.questions, 1):
        lines += [f'{i}. {q.question}', *[f'   {k}. {v}' for k, v in q.options.items()], '']
        if req.kind == 'answers':
            reference = q.answer if q.answer is not None else q.correct
            lines += [f'Reference: {reference if reference is not None else q.sample_answer}', q.explanation, '']
        else:
            lines += ['- [ ] I can explain this without notes' if req.kind == 'checklist' else 'Answer: ____________________', '']
    return '\n'.join(lines).encode()


@router.post('/study')
def export_study(req: ExportRequest):
    if sum(bool(v) for v in (req.questions, req.session_id, req.deck_id)) != 1:
        raise HTTPException(422, 'Choose one source: questions, a session, or a deck.')
    if req.session_id:
        from app.coach import connect, load, public
        with connect() as db:
            session = load(db, req.session_id, req.learner)
        if req.kind == 'answers' and not public(session)['done']:
            raise HTTPException(409, 'Finish the session before exporting its answer key.')
        req.questions = [ExportQuestion.model_validate(q) for q in session['questions']]
        req.title = session['topic'][:160]
    elif req.deck_id:
        from app.flashcards import get_deck
        deck = get_deck(req.deck_id)
        if not deck:
            raise HTTPException(404, 'Deck not found')
        req.questions = [ExportQuestion(question=c['front'], sample_answer=c['back']) for c in deck['cards'][:50]]
        req.title = deck['name'][:160]
    if not req.questions:
        raise HTTPException(422, 'There are no questions to export.')
    settings = get_settings()
    moderate(json.dumps({'title': req.title, 'questions': [q.model_dump() for q in req.questions]}),
             model=require_model(req.model), base_url=settings.ollama_base_url, timeout=settings.llm_timeout)
    try:
        body = render_pdf(req) if req.format == 'pdf' else render_markdown(req)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return Response(body, media_type='application/pdf' if req.format == 'pdf' else 'text/markdown',
                    headers={'Content-Disposition': f'attachment; filename="study-{req.kind}.{ "pdf" if req.format == "pdf" else "md"}"',
                             'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
