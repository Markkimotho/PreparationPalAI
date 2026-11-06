---
title: Build with us
description: Find a useful contribution, run PreparationPalAI locally, and understand the boundaries that keep study tools trustworthy.
hide:
  - toc
---

<div class="pp-contributor-hero" markdown>

<p class="pp-eyebrow">THE CONTRIBUTOR HANDBOOK</p>

# Make studying better, together.

This is the engineering side of PreparationPalAI: how it works, how to change it,
and how to operate it responsibly. You don’t need to know the entire stack to make
a useful contribution.

[Run the project](development.md){ .md-button .md-button--primary }
[Find a contribution](workflow.md){ .md-button }

</div>

## Choose your entry point

| I want to… | Read |
| --- | --- |
| Fix a UI problem or improve a study flow | [Development setup](development.md), then [add a feature](extending.md) |
| Understand the backend and model calls | [Architecture and project map](architecture.md) |
| Improve questions, citations, or feedback | [Tests and quality gates](testing.md) |
| Make the product guide clearer | [Maintain this documentation](documentation.md) |
| Host a shared workspace | [Workspace access](runbooks/security.md) and [deployment](runbooks/deployment.md) |
| Diagnose an outage | [Operational triage](runbooks/operations.md) |

## The boundaries that matter

- **User experience:** describe controls and learning tasks in the product guide;
  keep configuration and implementation details here.
- **Privacy:** keep documents, vectors, decks, and history scoped to the authorised workspace.
- **Evidence:** distinguish deterministic tests from actual model-quality evaluation.
- **Local inference:** use the configured Ollama service; do not introduce a silent cloud fallback.

See [implementation status](status.md) for work that still needs release validation.
If you are looking for help studying rather than changing the project,
[return to the user guide](/PreparationPalAI/).
