---
description: Operate local drawing submissions, review permissions, image validation and vision safety checks.
---
# Drawing answers and review

The frontend lazy-loads Excalidraw 0.18.1 when a drawing workspace is opened.
`frontend/scripts/drawing-assets.mjs` copies its fonts before development/build;
`EXCALIDRAW_ASSET_PATH` points to local assets. Keep these files in the production
build. Excalidraw is MIT licensed; the pinned upstream license is shipped under
`frontend/public/third-party-licenses/` and copied into the production bundle.
The package adds substantial lazy chunks, so diagram tools do not load with normal
text questions. Image tools, embeds, paste, cloud AI and external import are disabled.

The npm overrides patch vulnerable transitive `lodash-es` and `nanoid` releases.
Excalidraw retains the compatible nanoid 3 API; its Mermaid helper uses nanoid 5.
Re-run `npm audit`, build, and browser checks after changing these overrides.
Mermaid conversion is not exposed in this workspace.

## Question contracts

`study-v3` adds `drawing_required` and `drawing_prompt`. Generation schemas require
both fields, while older stored questions remain readable using defaults.
`app.drawing_requirements` normalizes explicit visual instructions if a model
mislabels them. Drawing tasks must be written-answer questions, never auto-graded
MCQs. The frontend also recognises explicit instructions in older questions and
always offers optional scratch drawing in Coach and Quiz Prep.

## Storage and access

`app.drawings` stores the normalized PNG and a vector-only editable scene in a
separate `drawings` table in the workspace’s coach SQLite database. Existing
database backups therefore include drawings. Submission ownership uses the
authenticated identity, not a caller-supplied learner ID. Readers can access only
their own submissions. Editors/admins can review their workspace’s queue. Local,
unauthenticated installations are a single trusted workspace, as elsewhere in the app.

Coach-linked submissions resolve the question and reference from server-owned
session data. The question index must still be active and within its deadline.
References are excluded from public submission responses. Reviews append to the
record inside a write transaction. Human scores remain separate from coach scores;
AI reviews never assign a score. Paginated listing preserves access to older work.

JSON request limits still apply. PNG input is limited to 1 MB and four million
pixels, decoded and re-encoded without metadata, composited on white and resized
to at most 1600 pixels per side. Editable scenes allow at most 1000 vector elements
and 500 KB; image/file/link/embedded elements are rejected. Downloads use no-store
responses and explicit attachment filenames. Unsaved browser drafts are memory-only;
local PNG/scene downloads remain available without model inference.

## Visual inference

The server checks the selected installed model’s `/api/show` capabilities. Without
`vision`, AI review returns 409 and leaves the submission pending. Do not infer
vision support from a model name or silently install a model.

Image inference uses a dedicated bounded Ollama adapter, rather than putting binary
image data into the text-only guard wrapper. It validates/moderates learner text,
then sends the actual normalized PNG through an image-aware safety classifier.
Only a literal boolean true with the expected schema permits the review call.
The second call uses the parameterized `drawing_review` prompt and a strict schema
requiring visible observations, feedback, improvements and reviewed/unclear status.
Output text passes the shared safety check before it is stored or released.
Potential context overflow, malformed output and unavailable inference fail closed.

Image safety and factual review remain model judgements, not guarantees. Submitted
learner images have not necessarily passed visual moderation before human review;
the viewer marks them as unreviewed and keeps them behind an explicit disclosure.
No images are posted to public galleries or sent through third-party drawing hosts.

## Validation

```bash
python -m pytest tests/test_drawings.py -q
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend audit
```

Tests cover actual bearer-key ownership/workspace isolation, review permissions,
PNG validation, image-aware safety failures, non-vision rejection, feedback history,
and a real image payload in the mocked visual-review transport. They do not establish
vision-model review quality. Test that separately with representative diagrams on
each installed vision model. The development machine used for this change has only
text-only Qwen 2.5 7B, so no live vision-quality claim is made.
