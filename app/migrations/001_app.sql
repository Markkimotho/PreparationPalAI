-- Hosted storage. Every table that holds a learner's data has a NOT NULL workspace column and an
-- index that starts with it (a test enforces this), and every query filters by workspace.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE app.flashcard_decks (
    workspace  TEXT NOT NULL,
    id         TEXT NOT NULL,
    body       JSONB NOT NULL,
    seq        BIGSERIAL,
    PRIMARY KEY (workspace, id)
);

CREATE TABLE app.coach_sessions (
    workspace TEXT NOT NULL,
    id        TEXT NOT NULL,
    learner   TEXT NOT NULL,
    body      JSONB NOT NULL,
    seq       BIGSERIAL,
    PRIMARY KEY (workspace, id)
);
CREATE INDEX coach_sessions_learner ON app.coach_sessions (workspace, learner, seq DESC);

CREATE TABLE app.drawings (
    workspace TEXT NOT NULL,
    id        TEXT NOT NULL,
    owner     TEXT NOT NULL,
    body      JSONB NOT NULL,
    image     BYTEA NOT NULL,
    seq       BIGSERIAL,
    PRIMARY KEY (workspace, id)
);
CREATE INDEX drawings_recent ON app.drawings (workspace, seq DESC);

CREATE TABLE app.ingestion_jobs (
    workspace TEXT NOT NULL,
    id        TEXT NOT NULL,
    owner     TEXT NOT NULL,
    kind      TEXT NOT NULL,
    payload   JSONB NOT NULL,
    state     TEXT NOT NULL,
    attempts  INTEGER NOT NULL DEFAULT 0,
    lease     DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated   DOUBLE PRECISION NOT NULL,
    result    JSONB,
    error     TEXT,
    run_token TEXT NOT NULL DEFAULT '',
    seq       BIGSERIAL,
    PRIMARY KEY (workspace, id)
);
CREATE INDEX ingestion_jobs_claim ON app.ingestion_jobs (workspace, state, lease);

CREATE TABLE app.workers (
    id        TEXT PRIMARY KEY,
    heartbeat DOUBLE PRECISION NOT NULL
);

CREATE TABLE app.usage_events (
    workspace TEXT NOT NULL,
    identity  TEXT NOT NULL,
    at        DOUBLE PRECISION NOT NULL
);
CREATE INDEX usage_events_window ON app.usage_events (workspace, identity, at);

-- 1024 dimensions: the gateway's embed-default (Qwen3-Embedding) supports Matryoshka sizes.
CREATE TABLE app.chunks (
    workspace  TEXT NOT NULL,
    collection TEXT NOT NULL,
    id         TEXT NOT NULL,
    source     TEXT NOT NULL DEFAULT '',
    page       INTEGER,
    content    TEXT NOT NULL,
    metadata   JSONB NOT NULL DEFAULT '{}',
    embedding  vector(1024) NOT NULL,
    PRIMARY KEY (workspace, collection, id)
);
CREATE INDEX chunks_source ON app.chunks (workspace, collection, source);
CREATE INDEX chunks_embedding ON app.chunks USING hnsw (embedding vector_cosine_ops);
