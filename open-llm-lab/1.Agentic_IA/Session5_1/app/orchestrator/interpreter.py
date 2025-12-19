from __future__ import annotations

import json
import re
from typing import Any

from pydantic import ValidationError

from app.core.config import AppConfig
from app.orchestrator.models import InterpreterOutput

try:
    from langchain_ollama import ChatOllama  # type: ignore
    from langchain_core.messages import HumanMessage, SystemMessage
except Exception:  # pragma: no cover
    ChatOllama = None  # type: ignore
    HumanMessage = None  # type: ignore
    SystemMessage = None  # type: ignore


def _guess_language(text: str) -> str:
    t = (text or "").lower()
    if any(ch in t for ch in ["¿", "¡"]) or any(w in t for w in ["qué", "quien", "quién", "por qué", "cómo"]):
        return "es"
    if any(w in t for w in ["che cos", "cos'è", "perché", "come"]):
        return "it"
    return "en"


def _strip_instruction(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^(investiga|busca|analiza|explora|dime)\s+(acerca\s+de|sobre|)\s*", "", t, flags=re.IGNORECASE)
    return t.strip()


class QueryInterpreter:
    def __init__(self, *, config: AppConfig) -> None:
        self._config = config

    def interpret(self, user_message: str) -> InterpreterOutput:
        base = _strip_instruction(user_message)
        input_language = _guess_language(user_message)

        # Best-effort LLM extraction if available; fallback is deterministic.
        if ChatOllama is not None:
            try:
                llm = ChatOllama(model=self._config.model_research_lead, base_url=self._config.ollama_base_url, temperature=0.0)
                system = SystemMessage(
                    content=(
                        "Return ONLY valid JSON matching this schema:\n"
                        "{\n"
                        '  "input_language": "es|en|it|fr|de|pt|...",\n'
                        '  "normalized_query": "string",\n'
                        '  "intent": "definition|biography|howto|comparison|open_question|...",\n'
                        '  "entities": ["..."],\n'
                        '  "keywords": ["..."],\n'
                        '  "constraints": {"time_range": null, "geo": null, "domain": null},\n'
                        '  "preferred_sources": ["wikipedia","encyclopedia","official","research"]\n'
                        "}\n"
                        "Rules: extract the TOPIC, not the instruction. Keep queries short keywords.\n"
                    )
                )
                human = HumanMessage(content=f"User message: {user_message}")
                msg = llm.invoke([system, human])
                raw = (getattr(msg, "content", "") or "").strip()
                data = json.loads(raw)
                return InterpreterOutput.model_validate(data)
            except Exception:
                pass

        intent = "open_question"
        norm = base or user_message.strip()
        if re.search(r"\b(qué es|what is|cos'?è)\b", user_message, re.IGNORECASE):
            intent = "definition"
        if re.search(r"\b(quién fue|who was|chi era)\b", user_message, re.IGNORECASE):
            intent = "biography"

        keywords = [w for w in re.findall(r"[\\w-]{3,}", norm.lower()) if w not in {"investiga", "sobre", "acerca"}]
        entities = []
        if norm:
            entities = [norm.strip()]

        return InterpreterOutput(
            input_language=input_language,
            normalized_query=norm,
            intent=intent,
            entities=entities[:3],
            keywords=keywords[:10],
            preferred_sources=["wikipedia"],
        )

