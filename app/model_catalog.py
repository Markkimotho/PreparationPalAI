"""One catalogue for all UI surfaces. Unknown capabilities stay unknown."""
from fastapi import HTTPException

from app.analysis import get_installed_models
from app.config import SUPPORTED_MODELS, get_settings


def catalogue(installed: set[str], supported: list[str] | None = None) -> list[dict]:
    settings = get_settings()
    recommendations = list(dict.fromkeys([
        *(supported if supported is not None else SUPPORTED_MODELS),
        settings.glm_model, settings.deepseek_model, *settings.extra_models,
    ]))
    metadata = {
        "qwen2.5:7b": ("Quizzes and structured answers", True, "Moderate memory; balanced speed"),
        "llama3.1:8b": ("Conversational study agent", True, "Moderate memory"),
        settings.glm_model: ("Multilingual study and recap", None, "9B default; check available RAM"),
        settings.deepseek_model: ("Multi-step reasoning and technical practice", None, "Reasoning can take longer"),
    }
    result = []
    for name in dict.fromkeys([*recommendations, *sorted(installed)]):
        use, tools, resources = metadata.get(name, (
            "General study; capabilities unverified", None, "Resource requirements unknown"))
        present = name in installed or (":" not in name and f"{name}:latest" in installed)
        result.append(dict(id=name, installed=present,
                           availability="installed" if present else ('unknown' if name in settings.extra_models else 'downloadable'),
                           recommended_use=use, tools=tools, structured_output=None,
                           resources=resources))
    return result


def require_model(model: str | None) -> str:
    name = model or get_settings().ollama_model
    installed = get_installed_models()
    if name not in installed and not (":" not in name and f"{name}:latest" in installed):
        raise HTTPException(409, detail=f"Model '{name}' is not installed or Ollama is offline. "
                            "Select it in the model picker and choose Pull, then retry.")
    return name
