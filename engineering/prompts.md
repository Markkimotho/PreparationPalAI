---
description: Configure learner profiles, maintain task-specific prompts, and evaluate local-model responses.
---
# Study prompts

`app/prompt_library.py` is the versioned source for the application’s study prompts.
The goal is clear tasks, explicit evidence rules and measurable outputs, rather
than relying on a model’s claimed expertise or making every prompt longer.

## Task contracts

| Task | Used by | Main checks |
| --- | --- | --- |
| `coach_questions` | Preparation Coach | Count, requested format, distinct questions, worked reference |
| `quiz_questions` | Quiz Prep and agent quizzes | Grounding, valid options, answer keys, supplied source names |
| `grade_answer` | Written-answer grading | Equivalent solutions, partial credit, 40/40/20 rubric |
| `flashcards` | Deck generation | Atomic recall, no repeated fronts, supported answers |
| `explain` | Concept explanations | Definition, mechanism, example, misconception |
| `document_qa` | Both RAG engines | Source-only claims, inline citations, explicit evidence gaps |
| `rewrite_question` | History-aware retrieval | Resolve references without answering or inventing context |
| `code_assistant` | Programming Assistant | Root cause, invariants, edge cases, honest test status |
| `study_agent` | Study Agent | Tool results, one-question flow, explicit web-search intent |
| `interview_followup` | Coach interviews | One relevant gap or tradeoff, hidden reference answer |
| `adaptive_question` | Coach recap/review | Scaffold the misconception and preserve question type |
| `document_analysis` | Analysis and insights | Findings versus interpretation, source-backed numbers |

Every task combines common epistemic rules, discipline checks, a task contract,
an output contract and a JSON data payload. Learner text, references, code and
documents remain data. Angle brackets in JSON values are escaped so they cannot
close the payload delimiter. This is one defence against prompt injection, not a
guarantee that a model will obey every instruction; application permissions and
validation must enforce the boundaries.

## Learner profiles

All model-backed HTTP requests accept an optional `profile` object. Existing
clients work without it. Defaults target an intermediate learner in English and
adapt to the topic without assuming a particular syllabus.

| Parameter | Default | Purpose |
| --- | --- | --- |
| `discipline` | `general` | Select field-specific checks; custom field names are allowed |
| `level` | `intermediate` | `beginner`, `intermediate`, or `advanced` |
| `objectives` | `[]` | Up to six concrete learning objectives |
| `language` | `English` | Response language; technical symbols retain their meaning |
| `notation` | empty | Units, sign conventions, symbol or notation preferences |
| `exam_context` | empty | Course, assessment context or interview requirements |

Specialised checks exist for mathematics, physics, chemistry, biology, medicine,
computer science, engineering, earth science, social science, humanities and
business. Other disciplines use the universal rules plus the supplied topic,
objectives and conventions. A profile is not a claim of accreditation or syllabus coverage.

For example, send this body to `POST /api/coach/sessions` using your normal workspace credentials:

```json
{
  "learner": "my-learner-id",
  "topic": "Thermodynamics: work and the first law",
  "mode": "recap",
  "difficulty": "hard",
  "question_type": "short_answer",
  "n": 3,
  "model": "qwen2.5:7b",
  "profile": {
    "discipline": "physics",
    "level": "advanced",
    "objectives": ["Apply the first law to a closed system", "Explain sign conventions"],
    "language": "English",
    "notation": "Use SI units; define the sign of work explicitly",
    "exam_context": "University thermodynamics revision"
  }
}
```

Profiles are available on `/api/chat/stream`, `/api/code-chat/stream`,
`/api/agent/stream`, `/api/quiz/generate`, `/api/quiz/validate`,
`/api/quiz/explain`, and `/api/flashcards/generate` too. The current UI uses defaults
and its visible topic, mode and difficulty controls; these profile fields are an
API option, not additional UI controls. Send the profile on each chat request.
Coach stores the profile and prompt version with the session, so grading and
follow-ups use the same settings. Old saved sessions use the default profile.
The agent passes its trusted profile and selected model to its study tools.

## Local-model constraints

Structured outputs use Ollama’s schema parameter as well as a schema in the prompt,
then validate the returned data with Pydantic. Quizzes, cards and coach sessions
generate at most two items per response, with one retry for invalid output. Duplicate
questions/card fronts are rejected. Coach requires the full count before saving a
session; document quizzes and cards may return fewer supported items. They continue
after a short batch and preserve previously validated items if a later batch still
fails after retry. Retry prompts include the validation feedback. Legacy JSON
arrays are still accepted when an older runner ignores the wrapper schema.

Long evidence payloads are capped at 12,000 characters with an explicit truncation
notice. This is a character limit, not an exact tokenizer budget: model, language,
history and schema overhead affect token usage. Keep the configured context/output
limits appropriate for the workload. More instructions cannot compensate for missing
evidence, an undersized context window, or a model unable to solve the problem.

See Ollama’s [structured-output guidance](https://docs.ollama.com/capabilities/structured-outputs)
for schema grounding and deterministic sampling. Keep temperature low for grading;
generation uses modest sampling rather than treating creativity as correctness.

## Change and evaluate

1. Update the relevant task and its semantic version when its contract changes.
2. Add a regression case for the actual failure, including malformed or adversarial inputs.
3. Run the deterministic suite. It checks wiring and contracts, not answer quality.
4. Run the live gate against installed models; never download a model implicitly.
5. Inspect representative responses with subject experts before claiming quality improvements.

```bash
python -m pytest tests -q
python -m scripts.quality_gate --live --model qwen2.5:7b --report quality-report.json
COACH_EVAL_MODELS=qwen2.5:7b python -m pytest evals/test_coach_eval.py -m eval -v
```

Quality reports record the prompt version and registry SHA-256 along with model
and dataset identifiers. Keep reports for each model/configuration. The current
science gate is a small grounding/formatting benchmark, not a lab-grade comparison,
comprehensive subject evaluation or resistance-to-injection certification.
