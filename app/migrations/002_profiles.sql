-- One profile per account: identity, look, and what the tutor tailors to (app/profile.py).
CREATE TABLE app.learner_profiles (
    workspace  TEXT PRIMARY KEY,
    body       JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
