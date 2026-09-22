---
description: Join an existing PreparationPalAI workspace or start a personal installation with Docker.
---
# Open or install PreparationPalAI

There are two ways to get started: use a workspace someone has set up for you,
or run PreparationPalAI on your own computer.

## Join an existing workspace

1. Open the **workspace address** supplied by your teacher, team, or administrator.
2. If a sign-in screen appears, enter your **Workspace access key**.
3. Open **Preparation Coach** to begin, or use **Knowledge base** to add material
   if your role permits it.

Your access key stays in the current tab’s memory. **Reloading the page signs you
out** on installations that require a key. Ask the administrator for a replacement
if your key stops working.

The GitHub Pages documentation address is not a hosted study workspace. You need
your workspace’s address to use the app.

## Run a personal installation

The simplest personal setup uses [Docker Desktop](https://www.docker.com/products/docker-desktop/)
or another Docker installation with Compose. The first start needs an internet
connection and several gigabytes of free disk space for local models.

After installing Docker, open a terminal and run:

```bash
git clone https://github.com/Markkimotho/PreparationPalAI.git
cd PreparationPalAI
docker compose up --build
```

Keep the terminal running. When startup finishes, open
[http://localhost:8000](http://localhost:8000) and select **Start preparing**, or go
directly to [Preparation Coach](http://localhost:8000/prepare).

The first start downloads the default chat and document-reading models. This can
take a while; later starts reuse the downloaded files. GLM and DeepSeek are
additional choices, not automatic first-start downloads.

!!! info "Why are models downloaded?"
    The model does the AI work on your installation. Downloading it first lets you
    study without sending inference requests to a paid cloud AI service. Optional
    web search still needs the internet.

### Return to your installation

From the same project folder, run `docker compose up` again. To stop the running
session, press **Ctrl+C** in its terminal. A normal stop and restart preserves
your saved study data.

Avoid commands that remove data volumes unless you intentionally want to delete
the installation’s stored material and history.

## What should I see?

The workspace has a sidebar, a model picker, and a **Knowledge base** control.
If the model is offline or a download fails, use [troubleshooting](../help/troubleshooting.md).

For a shared deployment, development setup, or a setup without Docker, use the
[contributor handbook](/PreparationPalAI/contribute/development/).
