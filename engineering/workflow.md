---
description: Propose a focused change, verify it, and prepare a reviewable pull request.
---
# Contribution workflow

## Find a focused contribution

Start with the [open issues](https://github.com/Markkimotho/PreparationPalAI/issues)
or a small problem you can reproduce. Useful contributions include clearer feedback,
better keyboard interactions, improved source handling, a representative evaluation
case, or a correction to the user guide.

For a larger design change, describe the learner problem and proposed behaviour
before investing in a broad implementation. Avoid coupling an unrelated refactor
to a focused product fix.

## Work in small steps

Create a branch, make a coherent change, run its relevant checks, and commit with
a concrete message. Keep commits frequent enough that a reviewer can follow the
decision boundaries, but avoid committing secrets, private documents, generated
site output, or local model files.

Preserve existing work in the branch. If the task overlaps another change, explain
the dependency rather than silently replacing it.

## Prepare the pull request

Describe the problem and resulting behaviour first. Include the relevant issue,
what was tested, and any meaningful limitation. For UI changes, include responsive
or interaction evidence. For model changes, distinguish mocked contract checks
from live evaluation results.

Do not claim a live model, deployment, or accessibility check passed if it was
skipped or unavailable. Keep incomplete work in draft and record what remains.

## Update the appropriate guide

Learner-visible changes belong in the [product guide](/PreparationPalAI/).
Engineering decisions and operational changes belong here. Build both portals
before submitting documentation changes.

Never include workspace keys, private prompts, source excerpts, or personal
documents in public issues or test fixtures. Use a minimal non-sensitive example.
