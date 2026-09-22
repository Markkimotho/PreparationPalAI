---
description: Implement a feature across the API and workspace while preserving privacy, local inference, and testability.
---
# Add a feature

Start with a concrete learner problem and a small acceptance scenario. A feature
is easier to review when its outcome can be described without naming a framework.

## Frontend changes

- Put a study surface under `frontend/src/sections/`.
- Register routes in `App.tsx` and sidebar entries in `sections/registry.tsx`.
- Reuse `ChatPanel`, `Markdown`, shared form controls, and theme tokens where appropriate.
- Route requests through `apiFetch`; direct `fetch` calls can accidentally omit workspace credentials.
- Account for loading, empty, error, keyboard, touch, and narrow-screen states.

Model-generated Markdown is untrusted. Remote images are deliberately not loaded
automatically, and mathematical rendering disables trusted HTML features.

## Backend changes

- Add request/response models for the HTTP contract and keep frontend types aligned.
- Keep routing thin and put behaviour in an engine module.
- Use the shared bounded model factory and configured Ollama endpoint.
- Resolve workspace context through the existing authentication boundary.
- Use durable jobs for slow ingestion rather than blocking an HTTP worker.
- Keep operational logs content-free. Do not log prompts, source text, filenames,
  raw provider exceptions, access keys, or browser error stacks.

For an API or stream change, cover the shape and failure behaviour in deterministic
tests. For quality changes, add representative evidence to the golden dataset or
live-evaluation cases as appropriate.

## Study and model changes

Do not infer capabilities from a model-family name. Record known capabilities or
leave them unverified. Keep the exact selected model identifier through every
request, and retain clear failures for unavailable models.

When changing generated assessments, check answer/reference consistency, format
validation, source labels, units, equivalent derivations, and failed-grading recovery.
Avoid presenting a model’s self-assessment as a calibrated measure of mastery.

## Document the product outcome

Update the relevant learner page under `docs/` when controls or behaviour change.
Put configuration, design decisions, and setup detail under `engineering/`.
See the [documentation guide](documentation.md) for the two-portal build.
