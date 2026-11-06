---
description: Ask source-backed questions about your notes and inspect the evidence behind an answer.
---
# Document chat

**Regular Chat** answers questions using indexed documents. Use it to clarify a
passage, compare ideas across notes, or find what your material says about a topic.

## Ask questions the material can answer

First, [add your material](material.md) and wait for it to appear in the source list.
Then open Regular Chat and try a focused request:

> Compare the assumptions behind the two methods in my notes. Cite the relevant pages.

> Explain the derivation in the uploaded chapter, keeping the intermediate steps and units.

> What does this material leave unclear about the experiment’s limitations?

## Check the references

Read the source labels supplied with the response. Use them to find the relevant
passage and compare it with the generated explanation. A citation can still be
misapplied; it is a way to check evidence, not proof of correctness by itself.

If the answer appears unrelated, narrow the question, check the source list, or
use more focused material. Diagrams and scanned equations may not extract cleanly.

## Follow up while the conversation is active

You can ask “why?”, request an example, or ask for a simpler explanation in the
same chat. Moving away or refreshing can lose the current conversation state.

The **LangChain / LangGraph** control selects an alternative conversation mode.
You can leave the default selected; you do not need to understand these implementation
names to use document chat. Changing modes can change the available chat history.

For practice on a topic without uploaded material, use
[Preparation Coach](coach.md) or [Study Agent](tutor.md).
