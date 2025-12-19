from __future__ import annotations

from ..llm_client import LLMClient
from .base import NodeResult, invoke_json


def run_final_decider(llm: LLMClient, model: str, bias: dict, analysis: dict, risk: dict) -> NodeResult:
    variables = {
        "bias": bias,
        "analysis": analysis,
        "risk": risk,
    }
    content, latency = invoke_json(llm, model, "final_decider", variables)
    summary = content.get("decision", "?") if isinstance(content, dict) else str(content)
    return NodeResult("final_decider", content, summary, latency)
