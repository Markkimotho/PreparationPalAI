---
description: Understand installed and downloadable models, GLM and DeepSeek choices, and how model selection affects study sessions.
---
# Choose a model

The selected model writes explanations, questions, and feedback. Different models
can vary in speed, reasoning, output format, and tool support. A larger or
“reasoning” model is not automatically the best choice for every task.

## Start with the available default

Use the installation’s default model for your first session. If you later change
models, keep the same topic and a few sample questions so you can compare usefulness,
not just the style of the prose.

**Model info** describes the recommended use, resource guidance, and capabilities
known by the application. **Unverified** means exactly that: do not assume the
capability or accuracy has been established.

## Understand the status

| Status | What to do |
| --- | --- |
| **Installed** | Select it and start a session |
| **Downloadable** | Choose Pull, if your role permits downloading models |
| **Unknown** | Ask the administrator to confirm the model tag and availability |
| **Unavailable: Ollama offline** | Restore the installation’s model connection before retrying |

On a personal installation, select an uninstalled model and choose **Pull**.
Where the model service supplies byte counts, download progress shows a percentage.
Wait for the ready message before beginning a session. A download can fail because
of a wrong tag, connectivity, available disk space, or server permissions.

In a shared workspace, model downloads require an administrator.

## GLM and DeepSeek

The default catalogue includes **GLM (`glm4:9b`)** and **DeepSeek (`deepseek-r1:7b`)**
alongside the existing model choices. Your administrator may configure different
tags, and other installed models can also appear.

Use the capability notes rather than the family name to decide whether a model
is suitable for Study Agent’s tools. A model can handle a written answer while
still struggling with agent actions or structured quiz output.

Each study section remembers its own model choice. An existing coach session
continues to use the model it started with; changing the top-bar choice affects
new sessions rather than regrading an old one.

!!! tip "When a model feels slow"
    Try fewer questions or a shorter written answer first. If necessary, select a
    smaller installed model. Downloads use disk space, and running models also
    needs memory; those are different requirements.

**Next:** [Troubleshoot a model problem](../help/troubleshooting.md#the-model-is-offline-or-missing)
