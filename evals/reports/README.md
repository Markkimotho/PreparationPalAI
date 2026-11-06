# Recorded local-model checks

## Study-v3 drawing routing

`study-v3-drawing-routing-qwen2.5-7b.json` records one live question-generation
check using a synthetic mechanics passage. The resulting written question has a
drawing requirement and a neutral pre-attempt brief. The report includes model,
prompt-registry and metadata-normalizer hashes. It tests routing and answer hiding,
including server normalization, rather than independent diagram-grading accuracy.
There was no vision-capable model installed, so visual AI review was tested with
mock transport and real image payloads, not a live vision-quality evaluation.

During development, a generated drawing task was initially marked text-only, and a
later model-generated brief exposed its reference solution. Required metadata plus
server normalization now correct explicit drawing instructions and replace briefs
with neutral guidance. The model's classification and wording are not trusted alone.

## Study-v2 guardrails

`study-v2-guardrails-qwen2.5-7b.json` is the unedited output of:

```bash
python -m scripts.check_study_guardrails --model qwen2.5:7b --report evals/reports/study-v2-guardrails-qwen2.5-7b.json
```

It checks safe physics, non-graphic clinical education, support-seeking, rejection
of suicide-method and explicit-sexual requests, an instruction-override attempt,
acceptance/rejection of relevant physics versus unrelated Bible evidence, valid
MCQ distractors and deliberately false propositions, and incorrect answer keys.
It records exact model, prompt and policy identifiers. This is a small same-model
classifier/verifier regression, not an independent safety or factual-quality audit.
The older report below predates these runtime checks and does not measure v2.

Separate end-to-end single-question generation attempts produced one withheld
response, followed by an accepted MCQ applying `F = ma` to 4 kg and 2 m/s² with
the correct answer 8 N. The withheld draft was not retained, so it cannot be
classified as a correct rejection or a false positive. These attempts are not
included in the classifier regression pass count and do not establish a generation
success rate.

## Study-v1 baseline

`study-v1-qwen2.5-7b.json` is the unedited output of:

```bash
python -m scripts.quality_gate --live --model qwen2.5:7b --report /tmp/preparationpal-prompt-quality-final-v3.json
```

It records the prompt registry hash, dataset hash, model/embedding digests and
Ollama version. On 6 November 2026, all four retrieval/citation/term-grounding cases
passed. Three of three requested quiz slots and two of three requested flashcard
slots met the existing gate’s checks. Partial generation counts against the
requested count; the thresholds were not changed to obtain a pass.

Separately, this command passed all four scientific grading cases (244.75 seconds):

```bash
COACH_EVAL_MODELS=qwen2.5:7b python -m pytest evals/test_coach_eval.py -m eval -q -x
```

Each case checks that a correct answer scores at least 70 and an incorrect answer
scores below 70. Cases cover force/units, stoichiometry, Hardy–Weinberg equilibrium
and variance of an independent sample mean. The grading contract was unchanged
between that run and the recorded retrieval/generation run.

These are small integration and regression checks. Term matching, formatting and
minimum answer length are not expert judgements of every claim. They establish no
lab-model equivalence, broad-domain accuracy or quality guarantee for other model
versions. GLM and DeepSeek were not evaluated in this run.
