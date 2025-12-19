from __future__ import annotations

from dataclasses import dataclass

try:
    from langchain_ollama import ChatOllama  # type: ignore
except Exception:  # pragma: no cover
    from langchain_community.chat_models import ChatOllama  # type: ignore

from app.core.config import AppConfig


@dataclass(frozen=True)
class RoleModels:
    planner: str
    researcher: str
    synthesizer: str
    guard: str
    reflector: str


FALLBACK_MODELS = [
    "llama3.1:8b",
    "qwen2.5:7b",
    "llama3:8b",
    "mistral:7b",
]


def _choose_model(preferred: str, available: set[str] | None) -> str:
    if available and preferred in available:
        return preferred
    if not available:
        return preferred
    for m in FALLBACK_MODELS:
        if m in available:
            return m
    return preferred


class LLMRouter:
    def __init__(self, config: AppConfig, available_models: set[str] | None = None):
        models = RoleModels(
            planner=_choose_model(config.model_planner, available_models),
            researcher=_choose_model(config.model_researcher, available_models),
            synthesizer=_choose_model(config.model_synthesizer, available_models),
            guard=_choose_model(config.model_guard, available_models),
            reflector=_choose_model(config.model_reflector, available_models),
        )
        self._base_url = config.ollama_base_url
        self._timeout = config.request_timeout_seconds
        self.models = models

    def chat(self, role: str, *, system: str, user: str, json_mode: bool = False) -> str:
        model_name = getattr(self.models, role)
        llm = ChatOllama(
            base_url=self._base_url,
            model=model_name,
            system=system,
            timeout=self._timeout,
            temperature=0.2,
            format="json" if json_mode else None,
        )
        msg = llm.invoke(user)
        return getattr(msg, "content", str(msg))
