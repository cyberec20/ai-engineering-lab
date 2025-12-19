from __future__ import annotations

from datetime import datetime, timezone

from ..llm_client import LLMClient
from .base import NodeResult, invoke_json


def run_explainer(llm: LLMClient, model: str, decision: dict, models_used: list[str]) -> NodeResult:
    variables = {
        "decision": decision.get("decision", "WAIT"),
        "reasons": decision.get("reasons", []),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "models": ", ".join(models_used),
    }
    content, latency = invoke_json(llm, model, "explainer", variables)
    return NodeResult("explainer", content, "narrative", latency)
