---
description: Ask Study Agent to explain, search, quiz, and follow up in a study conversation.
---
# Study Agent

Study Agent is a conversational tutor. It can inspect available topics, search for
web material, generate quiz questions, check answers, and explain concepts.

## Give it a useful starting request

Be specific about your subject, level, and the kind of help you want. For example:

> I’m revising undergraduate thermodynamics. Ask me one question at a time about
> the first law, then explain the assumptions behind any answer I miss.

> Help me prepare for a technical interview on probability. Start with conditional
> probability and ask me to justify each step.

> Explain binary search from my uploaded notes, then give me a boundary-case question.

Web search starts disabled. Select **Allow web search and add sources** when you
want the agent to find material online and save it to your knowledge base. This
requires an editor or administrator key in shared workspaces. Web searches contact
external services. Leave the box unchecked to work only with your existing material.

If your material does not cover the topic, the agent asks for relevant sources
instead of substituting questions from another subject. Successful quizzes also
offer [study-pack downloads](exports.md).

## Make it an active conversation

Answer before asking for the solution. Follow up with questions such as:

- “Which assumption in my answer is weakest?”
- “Give me a counterexample.”
- “Can you explain this at a simpler level, then ask me again?”
- “How would the answer change if this condition were removed?”

If a response conflicts with your notes, ask it to identify the supporting source
and verify that source yourself.

## Start a new session

Select **New session** when switching subjects or when the conversation has become
confusing. The current chat context is not a saved coach assessment.

!!! info "Model capabilities matter here"
    Study Agent depends on a model that can use tools. A model may work for normal
    chat but struggle to search or generate a quiz through the agent. If tools fail,
    try the installation’s default model or ask the administrator which models have
    been tested. See [choose a model](models.md).
