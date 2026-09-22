---
description: Resolve common sign-in, model, upload, quiz, and saved-session problems in PreparationPalAI.
---
# Troubleshooting

Start with the symptom you see. If you use a shared workspace, your administrator
can help with model downloads, storage, and service availability.

## The model is offline or missing

**Offline** means the workspace cannot currently reach its model service. On a
personal installation, check that the app and its Docker services are still running.
On a shared installation, contact the administrator.

**Not installed** means the selected model is unavailable on that installation.
Select an installed choice, or choose **Pull** if your role permits it. Wait for
the download to finish before retrying the session.

If a pull fails, confirm the tag and available disk space with the administrator.
Changing to a different model does not install the first one automatically.

## Responses are slow

The first request can take longer while a model loads. Larger models and long
written answers also take more time.

Try a shorter session, fewer questions, or a smaller installed model. Avoid
submitting the same request repeatedly while the current one is still working.
If a request times out, retry once after checking the model status.

## My upload failed or stays queued

1. Check the file type and size. By default, uploads allow three supported files
   up to 20 MiB each.
2. Open **Recent ingestion jobs** and inspect its state.
3. If it failed, try **Retry ingestion** after checking the app is online.
4. If it repeatedly fails, try a smaller PDF or a cleaner scan.

A queued job needs the installation’s ingestion worker. If nothing progresses,
contact the administrator. A refresh does not cancel a submitted job.

## The file uploaded, but answers don’t use it

Wait until ingestion is complete and the source is listed. Check that the topic
is actually covered in the file. Scanned equations, tables, diagrams, and handwritten
notes can extract poorly even when the file itself is accepted.

Ask Regular Chat a focused question about a passage you can verify. Use clearer
material or a text-based PDF if the extracted content seems incomplete.

## No quiz questions were generated

In **Quiz Prep**, you need relevant indexed material. **Preparation Coach** can
also work from general model knowledge without documents.

Try a narrower topic and fewer questions. If the model returns malformed questions,
retry or use another available model. Do not study from an obviously broken question.

## I disagree with the grading

Check the reference answer against your notes, including assumptions, units, and
equivalent valid derivations. Model-graded written answers can be wrong. Ask Study
Agent for an explanation, or check with your instructor or a reliable subject reference.

Treat the result as a signal for review, not as an official mark.

## My session or history disappeared

Chat conversations and the current Quiz Prep state can be lost when you navigate
away or refresh. Saved coach sessions are available in **Your recent sessions**.

Clearing browser storage, using a different browser profile, or changing workspaces
can make your saved learner history appear different. Ask the administrator before
deleting or resetting anything.

## Sign-in or permissions are stopping an action

Reloading a protected workspace clears the tab’s access key. Sign in again with
the key supplied by the administrator. Readers cannot directly upload or clear
material or change decks; model downloads require an administrator.

For a revoked or lost key, request a replacement. Never paste the key into a
public issue, chat transcript, or screenshot.

## Report a problem

Use the [GitHub issue tracker](https://github.com/Markkimotho/PreparationPalAI/issues)
for a reproducible product problem. Include the section, steps, model tag, and
visible error message. A request ID can help an administrator investigate.

Remove personal notes, private document names, access keys, and other sensitive
information before sharing screenshots or examples.
