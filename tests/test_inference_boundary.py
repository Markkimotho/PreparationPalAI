"""Backend-specific code stays behind the inference boundary."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'app'
CHAT_OWNERS = {'llm.py', 'embeddings.py'}
ENDPOINT_OWNERS = {'llm.py', 'analysis.py', 'diagnostics.py', 'api.py', 'model_catalog.py', 'embeddings.py',
                   'config.py', 'ui.py', 'exports.py', 'drawings.py'}


def sources():
    return {p.name: p.read_text() for p in APP.glob('*.py')}


def test_only_the_inference_layer_imports_provider_chat_clients():
    offenders = [name for name, text in sources().items()
                 if re.search(r'^\s*(from|import) langchain_(ollama|openai)', text, re.M) and name not in CHAT_OWNERS | {'safety.py'}]
    assert offenders == []


def test_features_build_models_only_through_the_factory():
    for name, text in sources().items():
        if name in {'llm.py', 'safety.py'}:
            continue
        assert 'ChatOllama(' not in text and 'ChatOpenAI(' not in text, name


def test_ollama_endpoint_is_not_used_by_feature_modules():
    for name in ('chain.py', 'graph.py', 'quiz.py', 'flashcards.py', 'coach.py', 'code_assistant.py', 'quiz_agent.py'):
        assert 'ollama_base_url' not in sources()[name], name
