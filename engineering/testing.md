---
description: Understand deterministic checks, live model evaluations, browser smoke checks, and container verification.
---
# Tests and quality gates

Use the smallest relevant check during implementation, then run the broader gate
before handing off. Keep three different kinds of evidence distinct.

## Deterministic application tests

```bash
python -m pytest tests -q
cd frontend
npm ci
npm test
npm run build
```

Backend tests mock inference and network operations where appropriate. Some tests
exercise real temporary Chroma stores with local fake embeddings to verify workspace
isolation. Frontend tests cover interactions and state transitions.

## Model-quality evaluation

```bash
python -m scripts.quality_gate --report /tmp/quality-contract.json
python -m scripts.quality_gate --live --model qwen2.5:7b --report /tmp/live-quality.json
```

The first command checks the dataset contract. The second measures actual retrieval,
citation, and evidence heuristics plus generated study-aid validity. It requires
installed models and uses an isolated temporary vector store.

For the fixed science-grading cases:

```bash
COACH_EVAL_MODELS='glm4:9b,deepseek-r1:7b' \
  pytest evals/test_coach_eval.py -m eval -v
```

These optional pytest cases skip unavailable models. The live **release gate**
fails rather than claiming success when required models are missing. Read
[the threshold policy](runbooks/quality.md) before approving a release.

## Responsive browser checks

Build the frontend, start the API on port 8018, then run:

```bash
CHECK_BROWSER=chrome python scripts/check_responsive.py
```

This uses mocked API dependencies and checks all workspace routes at 320, 375,
768, and 1440px, overflow, touch heights, focus restoration, and browser errors.
It is not a substitute for physical-device, screen-reader, or real-model testing.

## Container and deployment checks

CI builds the actual container and exercises PDF extraction, queued ingestion,
embeddings, RAG streaming, and frontend serving against a protocol stub. This
proves plumbing, not AI quality.

For a real installation, use `python -m scripts.deployment_smoke`. Its `--exercise`
option writes study material into the supplied workspace; use a disposable workspace.
See the [deployment runbook](runbooks/deployment.md).

## Documentation checks

```bash
pip install -r requirements-docs.txt
python scripts/build_docs.py
```

Both portals build in strict mode. The build checks local links, shared assets,
and separation of their search indexes. Documentation changes should not require
application dependencies, a model server, or a running Docker installation.
