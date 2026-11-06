---
description: Draw diagrams for practice questions and submit them for AI feedback or human review.
---
# Answer with a drawing

Some answers need more than a paragraph: a force diagram, a circuit, a molecular
structure, a labelled cell, a graph, or a geometric construction.

When a generated question asks for visual work, PreparationPalAI opens a drawing
workspace beside the question. You can also choose **Add a drawing** on a Coach
or Quiz Prep question to use it as scratch paper. Study Agent quizzes and diagram
instructions in chat can open the same tools.

## Draw and save

Use shapes, arrows, text labels and freehand drawing. The embedded editor is
[Excalidraw](https://github.com/excalidraw/excalidraw), a free open-source drawing
tool. It runs inside PreparationPalAI, with fonts served by your installation;
you do not need an Excalidraw account.

1. Read the drawing brief and create your diagram.
2. Add labels, directions, units, axes or assumptions where the question needs them.
3. Explain your drawing in the text box below it.
4. Choose **Submit drawing for review**.

Hiding the workspace preserves the current draft. **Save PNG** and **Save editable
drawing** keep local copies even if the model service is unavailable. Unsaved
drafts do not survive a page refresh or a change of question. A submitted drawing
is saved and appears under **Drawing reviews**.

Only shapes, lines, arrows and text are supported. External images, embedded pages
and links are disabled. If a drawing is too large, simplify it or save a local
copy. Submission requires the installation’s safety checks to be available.

## Request AI feedback

Open **Drawing reviews**, choose your submission, select an installed vision model,
and choose **Request AI review**. The model receives the actual drawing and your
explanation. It checks visible features, gives feedback and suggests improvements.
If the image is unclear, it should ask for clarification rather than invent details.

A vision-capable model is required. Text-only models, including `qwen2.5:7b`, cannot
inspect images. If none is installed, your drawing stays saved for human review;
ask the administrator to install a suitable vision model. The app does not download
one automatically. See [choosing a model](models.md).

AI feedback can misread diagrams and is not an official assessment. It does not
assign or change your exam score.

## Human review

An editor or administrator in your workspace can open a submitted drawing, read
the explanation, and add feedback with an optional score. Students with reader
keys see their own submissions and feedback; reviewers see their workspace’s queue.
Use **Load earlier submissions** to find older work.

AI and human feedback are kept in a history. Drawing reviews remain separate from
written-answer scores. Submit any written reasoning through the question’s normal
answer form. Coach-linked drawings must be submitted before that question finishes
or its exam timer expires.

You can download both the PNG and the editable `.excalidraw` file from a saved
submission. These downloads do not submit an answer to another application.
