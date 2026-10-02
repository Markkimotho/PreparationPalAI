# Contributing to PreparationPalAI

Thank you for helping make study and preparation more useful.

The [contributor handbook](https://markkimotho.github.io/PreparationPalAI/contribute/)
is the starting point for engineering work:

- [Run the project](engineering/development.md)
- [Understand the architecture](engineering/architecture.md)
- [Add a feature](engineering/extending.md)
- [Run tests and quality gates](engineering/testing.md)
- [Improve the documentation](engineering/documentation.md)
- [Prepare a focused pull request](engineering/workflow.md)

Keep changes focused, commit coherent steps, and describe the resulting behaviour
and relevant validation. Use non-sensitive examples in tests and reports. Never
commit workspace keys, private notes, model files, or generated documentation output.

Learner-facing instructions belong under `docs/`. Engineering references belong
under `engineering/`. Build both with `python scripts/build_docs.py` after installing
`requirements-docs.txt`.

If you are looking for help **using** PreparationPalAI, visit the
[user guide](https://markkimotho.github.io/PreparationPalAI/) instead.
