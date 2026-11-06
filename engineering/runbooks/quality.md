# Quality gates and release policy

For contributors evaluating changes and maintainers approving a release.

`evals/golden.json` is a versioned, non-sensitive science/algorithm dataset. The
offline gate validates its schema and source references. It is deliberately labelled
`offline-contract`; passing it does not establish model accuracy.

Run `python -m scripts.quality_gate --live --model <installed-tag> --report report.json`
for an actual isolated Chroma/Ollama benchmark. It measures retrieval recall@2,
source citation correctness, required evidence/forbidden claims, MCQ validity, and
flashcard structural validity. It uses a temporary vector collection and never
writes to the learner's knowledge base. Reports record dataset version, model tag
and digest, embedding tag, and Ollama version. No prompts or answers are uploaded
as CI artifacts. Exact-term evidence checks are conservative heuristics; they do
not replace subject-matter review, difficulty calibration, or a human usefulness
assessment of flashcards.

PR and nightly CI run deterministic backend/frontend tests, a production build,
and the offline dataset contract; JSON reports are archived. The separately
dispatched **Live model release gate** requires a trusted self-hosted runner
labelled `ollama`, with dependencies and model files already installed. Never run
untrusted fork code on a persistent runner. No models are downloaded automatically.

Release policy: the live report must pass on each recommended model before a
release is approved. Minimum retrieval, citation and evidence scores are 0.75;
quiz and flashcard validity must each reach 0.66. Missing models, provider errors,
and threshold regressions fail the live gate, not skip it. A model not passing the
gate stays unverified in the catalogue. Require the deterministic job in branch
protection and review the live report before tagging a release. Runner provisioning
and repository branch-protection settings remain administrator operations.
