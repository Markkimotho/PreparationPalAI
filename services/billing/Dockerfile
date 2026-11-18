FROM python:3.11-slim
RUN useradd --system --uid 10001 billing
WORKDIR /srv
COPY pyproject.toml ./
COPY billing ./billing
RUN pip install --no-cache-dir .
USER billing
CMD ["sh", "-c", "python -m billing.migrate && uvicorn billing.api:app --host 0.0.0.0 --port 8100"]
