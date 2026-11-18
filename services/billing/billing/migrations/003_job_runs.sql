-- Results of scheduled jobs, so the API's /metrics can report them (jobs run in another container).
CREATE TABLE billing.job_runs (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    problem     BOOLEAN NOT NULL,
    result      JSONB NOT NULL
);
CREATE INDEX job_runs_latest ON billing.job_runs (name, id DESC);
