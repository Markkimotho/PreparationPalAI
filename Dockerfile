# ── Stage 1: build the React SPA ─────────────────────────────────────────────
FROM node:22-alpine AS frontend
WORKDIR /frontend

# Install deps first for better layer caching.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

COPY frontend/ ./
RUN npm run build   # emits /frontend/dist

# ── Stage 2: FastAPI backend serving the built SPA ───────────────────────────
FROM python:3.12-slim
WORKDIR /app

# System deps: PDF OCR (tesseract/poppler) + lxml (libxml/xslt) for scraping.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    poppler-utils \
    libxml2-dev \
    libxslt-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY scripts/ ./scripts/

# Built SPA — api.py serves /app/frontend/dist at "/" when present.
COPY --from=frontend /frontend/dist ./frontend/dist

ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
RUN useradd --uid 10001 --create-home appuser && \
    mkdir -p /app/data/chroma /app/data/flashcards /app/data/coach /app/data/jobs /app/data/usage /app/data/pdfs && \
    chown -R appuser:appuser /app/data
USER appuser

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=3)"

EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
