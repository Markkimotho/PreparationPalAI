---
description: Set up the FastAPI backend, React frontend, and local model service for development.
---
# Development setup

The default development workflow uses a Python backend, a Vite frontend, and
Ollama. The documentation build is independent of all three.

## Prerequisites

- Python **3.11+**; CI and the container use Python 3.12.
- Node.js **22.12+** and npm.
- A running [Ollama](https://ollama.com/) service for real inference.
- Tesseract and Poppler if you need OCR; the application container includes them.

## Start the backend

```bash
git clone https://github.com/Markkimotho/PreparationPalAI.git
cd PreparationPalAI
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
uvicorn app.api:app --reload
```

On Windows, activate the virtual environment with `.venv\Scripts\activate`.
Install and start Ollama before using its commands.

## Start the frontend

In another terminal:

```bash
cd PreparationPalAI/frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` requests to the backend on port
8000. FastAPI exposes its interactive API reference at `http://localhost:8000/docs`.

To test the production frontend path, run `npm run build` in `frontend`, then
open the backend at `http://localhost:8000`. The public HTML landing page is served
by FastAPI; Vite’s root is the application during development.

## Run without downloading models

Deterministic tests mock model calls. They do not require model downloads:

```bash
python -m pytest tests -q
cd frontend
npm ci
npm test
npm run build
```

Do not treat a green mocked test suite as a claim that GLM, DeepSeek, or any other
model produces good answers. [Quality gates](testing.md) explain the separate checks.

## Configure only what you need

Use `.env.example` as the safe reference. Do not commit `.env` or real credentials.
Local mode uses a single workspace unless authentication is enabled.

The local API starts an embedded ingestion worker. For a separate process, set
`EMBEDDED_WORKER=false` and run `python -m app.jobs`. Docker starts its own worker.

For shared installations, use the [security](runbooks/security.md) and
[deployment](runbooks/deployment.md) runbooks rather than exposing development servers.
