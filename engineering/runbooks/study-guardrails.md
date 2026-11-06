---
description: Runtime safety, grounding review, agent permissions, and fillable study-pack boundaries.
---
# Study guardrails and exports

`app.llm.ChatOllama` is the inference entry point for every application model
feature, including the legacy analysis functions. Its sync and async generation
and streaming paths check input, buffer inference without token callbacks, and
moderate content and proposed tool arguments before release. There is no
environment switch that bypasses these checks.

`app.safety` uses a separate, temperature-zero structured-output call to the same
selected local model. Only a literal boolean decision with the expected schema is
accepted. Invalid JSON, unavailable inference, oversized input, or a context-window
boundary causes a closed failure. Common profanity also has a Unicode-normalized
deterministic backstop. Moderation calls intentionally use the underlying Ollama
class to avoid recursive moderation and do not inherit streaming callbacks.

Document-backed answers, analysis, agent responses and structured question/card
sets receive a second verifier pass for topic relevance, support and answer
consistency. This model review is fallible, especially because the generator and
judge share model weights. It is not a truth oracle, specialist assessment, or
comprehensive abuse classifier. Expand live adversarial evaluations before making
safety claims. Never reinterpret a malformed classifier response as permission.

Retrieval applies a conservative lexical admission check after vector top-k.
At least one meaningful query term must occur in the passage itself. Inventory
listing explicitly bypasses this check; teaching does not. This rejects the
reported Bible/physics mismatch, but can miss synonyms, translations, and implicit
references. Returning fewer sources is preferable to labelling unrelated passages
as evidence. Passing this check alone does not establish factual support.

Study Agent web access defaults off in both UI and API. Its request capability is
passed through hidden RunnableConfig and checked again inside the tool, together
with the request’s workspace role. Readers cannot mutate the KB through the agent.
Quiz and explanation tools return directly. Final quiz formatting consumes validated
tool data, hides references, and never substitutes generated text after tool failure.
Only final responses and structured quiz events reach SSE, not nested tool tokens.
The agent recursion budget is eight steps.

## Verification

```bash
python -m pytest tests/test_study_guardrails.py tests/test_study_exports.py -q
python -m scripts.check_study_guardrails --model qwen2.5:7b --report /tmp/study-guardrails.json
```

The live check records model and policy hashes and expected/actual decisions.
Infrastructure failures do not count as successful rejection. It never downloads
models or modifies a knowledge base. The recorded regression is small; GLM and
DeepSeek need separate runs. Normal CI uses mocks and a protocol stub, which do
not establish model quality.

## Study packs

`POST /api/exports/study` accepts exactly one source: up to 50 question objects,
a workspace-scoped coach session plus learner ID, or a workspace-scoped deck ID.
Coach answer keys require a finished session. Exports are moderated again and
returned as attachments with `Cache-Control: no-store`.

PyMuPDF creates AcroForm text, choice and checkbox widgets. Exam/worksheet/checklist
generation never writes reference answers into page text, metadata, or hidden
form fields. Answer keys are separate documents. All incoming strings are escaped
before HTML layout; no remote images, scripts or styles are inserted. Unicode
font fallback handles scientific symbols. Complex LaTeX is preserved as text,
not typeset. PDF overflow fails explicitly; Markdown remains available.

Tests inspect fields, check answer-key separation, save/reopen filled forms, and
verify Unicode extraction. Render exported pages to PNG and inspect them whenever
layout changes. Form support varies by PDF reader. Exported responses do not write
back to online assessments.
