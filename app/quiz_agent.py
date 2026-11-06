"""LangGraph tool-calling agent for interactive exam preparation.

The agent orchestrates five tools:
  - search_and_add_to_kb  : scrape + ingest web content on any topic
  - make_quiz             : generate questions from the knowledge base
  - check_answer          : grade a student answer with feedback
  - explain               : deep-dive explanation from knowledge base
  - list_topics           : summarise what's in the knowledge base

A module-level MemorySaver checkpointer means conversation threads survive
across multiple Streamlit reruns as long as the process stays alive.
"""

import json
import logging
from collections.abc import Iterator

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from app.llm import ChatOllama
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from app.config import get_settings
from app.prompt_library import PromptProfile, render_prompt
from app.workspace import scoped_thread, role
from app.quiz import explain_concept, generate_questions, validate_answer
from app.retriever import get_retriever
from app.scraper import search_and_scrape
from app.vectorstore import get_doc_count, ingest_documents

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────

# Single shared checkpointer — keeps thread history across Streamlit reruns.
_checkpointer = MemorySaver()

# ── Tools ─────────────────────────────────────────────────────────────────────


def _study_parameters(config: RunnableConfig | None) -> dict:
    cfg = (config or {}).get('configurable', {})
    result = {}
    if cfg.get('model'):
        result['model'] = cfg['model']
    if cfg.get('profile'):
        result['profile'] = PromptProfile.model_validate(cfg['profile'])
    return result


@tool
def search_and_add_to_kb(topic: str, num_results: int = 3, config: RunnableConfig = None) -> str:
    """Search the web for a topic and add the found content to the knowledge base.

    Use when the user wants to study something not yet in the knowledge base,
    or when they say 'scrape', 'find', 'search', or 'look up' content online.

    Args:
        topic: The topic to search for (e.g. "Python async/await", "System Design basics")
        num_results: Number of web pages to scrape (1-5, default 3)
    """
    if not (config or {}).get('configurable', {}).get('allow_web') or role.get() == 'reader':
        return 'Web search is disabled. Enable web access for this message with an editor or admin key.'
    try:
        chunks = search_and_scrape(topic, num_results=max(1, min(num_results, 5)))
        if not chunks:
            return (
                f"No content found for '{topic}'. "
                "Try a more specific search term or upload a document instead."
            )
        count = ingest_documents(chunks)
        return (
            f"Added {count} chunks about '{topic}' to the knowledge base "
            f"from {num_results} web page(s). You can now generate quiz questions on this topic."
        )
    except Exception as exc:
        logger.exception("search_and_add_to_kb failed")
        return f"Web search failed: {exc}"


@tool(return_direct=True)
def make_quiz(
    topic: str,
    question_type: str = "mcq",
    n: int = 5,
    difficulty: str = "medium",
    exam_type: str = "general exam",
    config: RunnableConfig = None,
) -> str:
    """Generate quiz questions from the knowledge base on a given topic.

    Use when the user asks to be quizzed, tested, or wants practice questions.

    Args:
        topic: Subject/topic to generate questions about
        question_type: "mcq" (multiple choice), "true_false", "short_answer", or "mixed"
        n: Number of questions (1-20, default 5)
        difficulty: "easy", "medium", "hard", or "mixed"
        exam_type: e.g. "general exam", "technical interview", "job interview", "certification"
    """
    questions = generate_questions(
        topic=topic,
        question_type=question_type,
        n=max(1, min(n, 20)),
        difficulty=difficulty,
        exam_type=exam_type,
        **_study_parameters(config),
    )
    if not questions:
        return (
            f"Could not generate questions for '{topic}'. "
            "The knowledge base may lack content on this topic. "
            "Ask the learner to upload relevant material. Do not invent replacement questions."
        )
    return json.dumps(questions, indent=2)


@tool
def check_answer(
    question: str,
    correct_answer: str,
    student_answer: str,
    question_type: str = "short_answer",
    config: RunnableConfig = None,
) -> str:
    """Grade a student's answer and return detailed feedback.

    Use after presenting a question to evaluate the student's response.

    Args:
        question: The full question text
        correct_answer: The correct answer or reference sample answer
        student_answer: What the student answered
        question_type: "mcq", "true_false", or "short_answer"
    """
    result = validate_answer(
        question=question,
        correct_answer=correct_answer,
        student_answer=student_answer,
        question_type=question_type,
        **_study_parameters(config),
    )
    if result.get('feedback', '').startswith('Could not grade answer:'):
        return json.dumps({'error': 'The model could not grade this answer. Retry; no score has been awarded.'})
    return json.dumps(result)


@tool(return_direct=True)
def explain(concept: str, config: RunnableConfig = None) -> str:
    """Get a detailed explanation of a concept from the knowledge base.

    Use when the user says 'explain', 'what is', 'describe', or 'help me understand'.

    Args:
        concept: The concept, term, or topic to explain in detail
    """
    return explain_concept(concept, **_study_parameters(config))


@tool
def list_topics() -> str:
    """List the main topics available in the current knowledge base.

    Use when the user asks what's available to study, what topics exist,
    or what they can be quizzed on.
    """
    count = get_doc_count()
    if count == 0:
        return (
            "The knowledge base is empty. You can:\n"
            "1. Upload PDF/TXT documents using the sidebar\n"
            "2. Ask me to search the web for a topic (e.g., 'search for Python basics')"
        )
    retriever = get_retriever(top_k=20, inventory=True)
    try:
        docs = retriever.invoke("main topics")
        sources = sorted({doc.metadata.get("source", "unknown") for doc in docs})
        source_list = ", ".join(sources[:12])
        suffix = " (and more...)" if len(sources) > 12 else ""
        return (
            f"Knowledge base: {count} indexed chunks.\n"
            f"Sources: {source_list}{suffix}"
        )
    except Exception:
        return f"Knowledge base: {count} indexed chunks."


# ── Agent ─────────────────────────────────────────────────────────────────────

_TOOLS = [search_and_add_to_kb, make_quiz, check_answer, explain, list_topics]

_SYSTEM_PROMPT = render_prompt('study_agent')


def invoke_agent(
    message: str,
    thread_id: str = "default",
    model: str | None = None,
    profile: PromptProfile | None = None,
    allow_web: bool = False,
    include_questions: bool = False,
) -> str:
    """Send a message to the quiz agent and return its text response.

    The shared _checkpointer keeps conversation state across calls with
    the same thread_id for as long as the process is alive.
    """
    settings = get_settings()
    llm = ChatOllama(
        model=model or settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.2,
        keep_alive=settings.ollama_keep_alive,
    )
    agent = create_react_agent(
        llm,
        [t for t in _TOOLS if t.name != 'search_and_add_to_kb' or (allow_web and role.get() != 'reader')],
        prompt=render_prompt('study_agent', profile=profile),
        checkpointer=_checkpointer,
    )
    try:
        result = agent.invoke(
            {"messages": [HumanMessage(content=message)]},
            config={"recursion_limit": 8, "configurable": {"thread_id": scoped_thread(thread_id), "model": model,
                                     "profile": profile.model_dump() if profile else {}, "allow_web": allow_web}},
        )
        messages = result.get("messages", [])
        answer = _final_answer(messages)
        if include_questions:
            return answer, _quiz_items(messages)
        return answer
    except Exception as exc:
        logger.exception("Agent invocation failed")
        from app.safety import SafetyError
        answer = str(exc) if isinstance(exc, SafetyError) else 'The study request failed. Please retry or upload relevant material.'
        return (answer, []) if include_questions else answer


def stream_agent(
    message: str,
    thread_id: str = "default",
    model: str | None = None,
    profile: PromptProfile | None = None,
    allow_web: bool = False,
) -> Iterator[tuple[str, object]]:
    """Stream the agent's response token-by-token.

    Yields one checked ("token", str) final response, then optional validated
    ("questions", list) for study-pack export. Nested tool tokens are withheld.
    """
    # LangGraph's messages stream includes nested generation inside tools.
    # Release only the completed result, never reasoning or raw tool JSON.
    answer, questions = invoke_agent(message, thread_id, model, profile, allow_web, include_questions=True)
    yield ('token', answer)
    if questions:
        yield ('questions', questions)


def _quiz_items(messages):
    from app.quiz import QuizItem
    start = max((i for i, m in enumerate(messages) if m.type == 'human'), default=-1)
    items = []
    for msg in messages[start + 1:]:
        if msg.type == 'tool' and msg.name == 'make_quiz':
            try:
                items.extend(QuizItem.model_validate(q).model_dump() for q in json.loads(msg.content))
            except (ValueError, TypeError):
                return []
    return items


def _final_answer(messages) -> str:
    # Only inspect this turn. Historical tool successes must not override the
    # current request or mask a failed generation.
    start = max((i for i, m in enumerate(messages) if m.type == 'human'), default=-1)
    quiz_results = [m for m in messages[start + 1:] if m.type == 'tool' and m.name == 'make_quiz']
    if quiz_results:
        from app.quiz import QuizItem
        sections = []
        for result in quiz_results:
            try:
                questions = [QuizItem.model_validate(q) for q in json.loads(result.content)]
                if not questions:
                    raise ValueError('Empty quiz')
            except (ValueError, TypeError):
                return 'I could not create a grounded quiz on that topic. Upload relevant material or enable web access and ask me to search. No replacement questions have been invented.'
            for q in questions:
                sections.append(f'### {len(sections) + 1}. {q.question}\n\n' +
                    '\n'.join(f'- **{k}.** {v}' for k, v in q.options.items()))
        return '\n\n'.join(sections) + '\n\nReply with your answers when you are ready.'
    for msg in reversed(messages[start + 1:]):
        if msg.type == 'tool' and msg.name == 'check_answer':
            try:
                result = json.loads(msg.content)
                if result.get('error'):
                    return result['error']
                return f"**Score: {result['score']}/100**\n\n{result.get('feedback', '')}\n\n{result.get('hint', '')}"
            except (ValueError, TypeError, KeyError):
                return 'I could not grade that answer reliably. Please retry.'
    return messages[-1].content if messages else 'No response from agent.'
