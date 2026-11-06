# Workspace access

This reference is for workspace administrators and maintainers. For learner-facing
sign-in help, use the [product guide](https://markkimotho.github.io/PreparationPalAI/help/privacy/).

Local development defaults to a single `local` workspace. Enable authentication
before exposing the API outside a trusted machine. `PRODUCTION=true` refuses to
start unless `AUTH_ENABLED=true` and `AUTH_TOKENS` is configured.

Each bearer key maps to one workspace and role. Configure only SHA-256 digests:

```json
{"<64-character-sha256-digest>": {"workspace": "science-class", "role": "editor"}}
```

Set this JSON in the server-only `AUTH_TOKENS` environment variable. Generate a
random 32-byte key using a password manager or `openssl rand -hex 32`, and compute
its SHA-256 digest. Give the raw key to the intended user through a private channel.
Never commit raw keys or hashes to application code. Revoke a key by removing its
digest and restarting the service. Rotate keys by adding the replacement digest,
distributing the new key, then removing the old digest.

All `/api/*` routes except `/api/auth/status` require the bearer key. `/metrics`
requires an admin key. Public marketing pages remain public. Reader keys can use
study tools but cannot upload, clear, or modify decks. Editors can modify workspace
material. Only administrators can download server-wide models.

Storage paths, vector-store clients, conversation/checkpoint thread IDs, flashcards,
coach history, and later ingestion jobs are scoped by the authenticated workspace.
Client-supplied workspace headers are ignored. Keys belonging to the same workspace
intentionally share material and conversation IDs. Use distinct workspaces for
private users. The coach's learner ID distinguishes learning profiles within a
workspace; it does not grant access to another workspace.

Use HTTPS at the reverse proxy. The browser holds its key in memory, never in the
bundle or persistent browser storage. Reloading requires signing in again. There
are no authentication cookies, so cross-site requests cannot automatically attach
credentials. Close the tab to clear browser credentials. The legacy Streamlit and
CLI interfaces are operator tools and must not be published as authenticated APIs.
