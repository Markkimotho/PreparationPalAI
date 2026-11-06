# PreparationPalAI

Study deeply. Prepare confidently.

Turn your notes and difficult questions into focused practice for exams, technical
interviews, and everyday learning. Use local AI to test your reasoning, review
mistakes, and decide what to revisit.

**[Read the user guide](https://markkimotho.github.io/PreparationPalAI/)** ·
**[Contributor handbook](https://markkimotho.github.io/PreparationPalAI/contribute/)**

## Choose your next study step

| Your goal | Where to start |
| --- | --- |
| Understand a topic and test recall | Preparation Coach → Learn & recap |
| Practise under exam conditions | Preparation Coach → Exam practice |
| Explain your approach and handle follow-ups | Preparation Coach → Technical interview |
| Revisit concepts you missed | Preparation Coach → Weak-area review |
| Ask questions about your notes | Regular Chat |
| Study with a conversational tutor | Study Agent |
| Make short prompts for active recall | Flashcards |
| Discuss code, debugging, and trade-offs | Programming Assistant |

Upload PDFs or images, add a web topic, or start a coach session using labelled
general model knowledge. The model catalogue includes configurable GLM and
DeepSeek choices alongside the default Qwen model.

## Get started

Already have a workspace address? Open it and use the access key supplied by your
administrator if asked. Follow [your first study session](docs/start/first-session.md).

For a personal installation, install Docker with Compose, then run:

```bash
git clone https://github.com/Markkimotho/PreparationPalAI.git
cd PreparationPalAI
docker compose up --build
```

Open **http://localhost:8000** when startup finishes. The first start builds the app
and downloads the default chat and document-reading models, so allow time and
several gigabytes of free storage. Later starts reuse the downloaded files.

Read [open or install PreparationPalAI](docs/start/access.md) for the full walkthrough.
The documentation website is a guide; it does not host your study workspace.

## Build understanding, not just a score

Use your syllabus and trusted material to choose the topic. Answer before looking
at the reference, explain assumptions and units, and review the source when a model
answer seems questionable. Generated questions and scores are practice feedback,
not official marking schemes or a guarantee of exam or interview results.

Inference uses your installation’s configured Ollama service. Web search and model
downloads contact external services. In shared installations, workspace access
controls determine who can use the stored material.

## Find help

- [Prepare for an exam](docs/playbooks/exams.md)
- [Practise a technical interview](docs/playbooks/interviews.md)
- [Recap a topic](docs/playbooks/recap.md)
- [Troubleshooting](docs/help/troubleshooting.md)
- [Privacy and workspaces](docs/help/privacy.md)

## Improve the project

The engineering documentation lives separately in the
**[contributor handbook](https://markkimotho.github.io/PreparationPalAI/contribute/)**.
Start with [development setup](engineering/development.md),
[architecture](engineering/architecture.md), or the
[contribution workflow](CONTRIBUTING.md). Security, configuration, tests, deployment,
and recovery are documented there rather than in the learner guide.
