---
description: Understand personal and shared workspaces, what is saved, and when the app contacts external services.
---
# Privacy and workspaces

## Personal versus shared

On a personal installation, your app data is stored on the machine running
PreparationPalAI. On an installation managed by someone else, that administrator
controls the server and its stored data.

A **workspace** is a boundary for indexed material, decks, conversations, and study
history. People with keys for the same workspace intentionally share access to
workspace material. It is not automatically private from classmates or colleagues
who have access to that workspace.

Ask who can access your workspace before uploading personal or confidential notes.

## Access keys and roles

Protected installations use a workspace access key supplied by the administrator.
The key stays in the current tab’s memory, so refreshing requires signing in again.

| Role | Typical access |
| --- | --- |
| **Reader** | Use study tools and read existing workspace material |
| **Editor** | Also upload/clear material and create or change flashcard decks |
| **Administrator** | Also manage server-wide model downloads |

Your browser’s learner identifier helps organise coach history inside a workspace.
It is not a separate password or a private account boundary within a shared workspace.

## When information leaves the installation

AI inference uses the configured Ollama service. A personal installation normally
runs that service on your own machine; a managed workspace may use its operator’s server.
The app does not automatically fall back to a cloud AI provider.

Optional **web search** contacts external services using the search topic. Model
downloads also need the internet. Avoid entering private information as a web-search
topic. The documentation website does not receive your uploaded study material.

## What persists

Indexed material, flashcard decks, and coach sessions persist across normal server
restarts. Current chat context and in-progress Quiz Prep state are less durable.
Clearing browser storage can change which learner profile the browser presents.

Clearing the knowledge base does not mean every flashcard or previous coach answer
has been deleted. These are separate saved records. Wait for active ingestion jobs
to finish before clearing material, and ask the administrator about deletion or
retention of the installation’s stored data and backups.

!!! tip "Before sharing a problem report"
    Remove workspace keys, personal notes, document names, and private prompts.
    Share a small non-sensitive example that demonstrates the problem instead.
