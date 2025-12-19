from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from server.llm_client import LLMClient

PROMPTS_PATH = Path(__file__).resolve().parent.parent / "prompts" / "nodes.yaml"


@dataclass
class NodeResult:
    name: str
    content: Any
    summary: str
    latency_ms: int


def load_prompts() -> dict[str, str]:
    data = yaml.safe_load(PROMPTS_PATH.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in data.items()}


PROMPTS = load_prompts()


def _normalize_payload(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("```", 1)[0]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def invoke_json(llm: LLMClient, model: str, prompt_key: str, variables: dict[str, Any]) -> tuple[Any, int]:
    text, latency = llm.invoke(model, PROMPTS[prompt_key], variables)
    payload = _normalize_payload(text)
    try:
        return json.loads(payload), latency
    except Exception:
        return {"raw": payload}, latency
