---
description: Map the frontend, API, model engines, workspace boundaries, and persistent stores.
---
# Architecture and project map

PreparationPalAI has a React workspace, a FastAPI adapter, and specialised study
engines backed by Ollama. The API translates requests and streaming events; it
delegates learning behaviour to modules under `app/`.

## Repository map

```text
app/                     API, study engines, workspace access, queue and metrics
frontend/src/
  sections/              Coach, Quiz Prep, Study Agent, chat, code, flashcards
  components/            Shared shell, model picker, knowledge base, Markdown
  context/               Model preferences and knowledge-base state
  api/                   Typed JSON client, authentication transport, SSE parser
tests/                   Deterministic backend and isolation tests
evals/                   Versioned dataset and optional real-model evaluations
scripts/                 Quality gates, smoke checks, backup and restore
docs/                    Learner-facing product guide
engineering/             This contributor handbook and operational runbooks
docs_theme/              Shared documentation brand and templates
monitoring/              Prometheus rules and Grafana/Loki configuration
```

## A study request

1. The browser sends JSON or a multipart upload through the shared authenticated transport.
2. Authentication resolves the workspace and role; budgets apply to accepted API POSTs.
3. The route calls the relevant engine. Retrieval uses a workspace-scoped Chroma client.
4. The bounded model factory applies context, output, connection, and HTTP limits.
5. Chat surfaces return SSE frames. Other operations return typed JSON.

The UI parses POST-based streams rather than using `EventSource`, since requests
carry JSON bodies and bearer authentication.

## Engine modules

| Area | Entry points |
| --- | --- |
| Saved adaptive preparation | `app/coach.py` |
| Document RAG | `app/chain.py` and `app/graph.py` |
| Tool-using tutor | `app/quiz_agent.py` |
| Coding conversation | `app/code_assistant.py` |
| Quiz generation and grading | `app/quiz.py` |
| Flashcard store and generation | `app/flashcards.py` |
| Model catalogue and preflight | `app/model_catalog.py` |
| Bounded model construction | `app/llm.py` and `app/embeddings.py` |

The older Streamlit UI and multi-model analysis remain operator/development tools.
Do not publish them as substitutes for the authenticated API.

## Ingestion and persistence

The browser enqueues uploads or topic searches. A worker claims jobs, renews a
lease, extracts or fetches text, embeds chunks, and upserts vectors. File extraction
runs in a child process with a deadline. Retries use deterministic chunk IDs.

Chroma stores indexed documents; JSON files store flashcard decks; SQLite stores
coach sessions, ingestion jobs, and usage budgets. Model files are managed by Ollama.
Different stores have different durability and backup requirements.

## Workspace boundaries

Request context scopes storage paths and conversation/checkpoint IDs. Do not use a
client-supplied workspace name to select storage. Keys for the same workspace
intentionally share material; the browser learner ID is not a second authentication layer.

Before changing retrieval, queue execution, or memory, read
[workspace access](runbooks/security.md) and preserve cross-workspace tests.
The default file/SQLite/embedded-Chroma topology is intended for a single host.
