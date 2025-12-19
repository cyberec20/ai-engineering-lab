from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langchain_ollama import ChatOllama  # type: ignore
except Exception:  # pragma: no cover
    ChatOllama = None  # type: ignore

from app.core.config import AppConfig
from app.orchestrator.models import QueryInterpretation


def _detect_language_heuristic(text: str) -> str:
    t = (text or "").strip().lower()
    if any(ch in t for ch in ("¿", "¡")):
        return "es"
    if re.search(r"\b(que|qué|quien|quién|como|cómo|por|para|sobre|acerca)\b", t):
        return "es"
    if re.search(r"\b(cos'è|chi|come|perché)\b", t):
        return "it"
    return "en"


def _normalize_query_heuristic(text: str) -> tuple[str, list[str], list[str], str]:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    lowered = cleaned.lower()
    intent = "open_question"
    if any(w in lowered for w in ("que es", "qué es", "cos'è", "what is")):
        intent = "definition"
    if any(w in lowered for w in ("quien fue", "quién fue", "who was", "biografia", "biography")):
        intent = "biography"
    m = re.search(r"(?:sobre|acerca de|about)\s+(.+)$", lowered)
    subject = cleaned
    if m:
        subject = cleaned[m.start(1) :].strip()
    subject = re.sub(r"^(investiga|investigar|research|analyze|analiza)\s+", "", subject, flags=re.I).strip()
    entities = [subject] if subject else []
    keywords: list[str] = []
    if intent == "definition":
        keywords = ["definition", "tcp/ip"] if _detect_language_heuristic(cleaned) != "es" else ["definicion", "tcp/ip"]
    return subject or cleaned, entities, keywords, intent


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = re.search(r"\{.*\}", text, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


class QueryInterpreter:
    def __init__(self, *, config: AppConfig) -> None:
        self._config = config

    def interpret(self, user_message: str) -> QueryInterpretation:
        if not self._config.enable_llm_query_interpreter or ChatOllama is None:
            return self._fallback(user_message)

        system = SystemMessage(
            content=(
                "You are a strict JSON generator. Output ONLY valid JSON.\n"
                "Task: infer the user's input language and extract a normalized search query.\n"
                "Rules:\n"
                "- Separate topic vs instruction (e.g., 'Investigate Isaac Newton' -> topic 'Isaac Newton').\n"
                "- Queries must be keywords, not long questions.\n"
                "- Keep arrays short.\n"
                "Return JSON with keys: input_language, normalized_query, intent, entities, keywords, constraints, preferred_sources."
            )
        )
        human = HumanMessage(content=user_message)
        llm = ChatOllama(model=self._config.model_research_lead, base_url=self._config.ollama_base_url, temperature=0)
        msg = llm.invoke([system, human])
        raw = getattr(msg, "content", "") or ""
        data = _extract_json(raw)
        if not isinstance(data, dict):
            return self._fallback(user_message)
        try:
            return QueryInterpretation.model_validate(data)
        except Exception:
            return self._fallback(user_message)

    def _fallback(self, user_message: str) -> QueryInterpretation:
        lang = _detect_language_heuristic(user_message)
        normalized, entities, keywords, intent = _normalize_query_heuristic(user_message)
        return QueryInterpretation(
            input_language=lang,
            normalized_query=normalized,
            intent=intent,
            entities=entities,
            keywords=keywords,
            constraints={},
            preferred_sources=["wikipedia", "encyclopedia"],
        )
