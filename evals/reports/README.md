# Recorded local-model checks

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
