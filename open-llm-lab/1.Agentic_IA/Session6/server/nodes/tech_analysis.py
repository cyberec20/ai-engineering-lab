from __future__ import annotations

from ..llm_client import LLMClient
from .base import NodeResult, invoke_json


def run_tech_analysis(llm: LLMClient, model: str, insight: dict) -> NodeResult:
    variables = {"symbol": insight.get("symbol", "XAUUSD"), "insight": insight}
    content, latency = invoke_json(llm, model, "tech_analysis", variables)
    if isinstance(content, dict):
        signals = content.get("signals", [])
        if isinstance(signals, list):
            summary = ", ".join([str(sig) for sig in signals])
        else:
            summary = str(signals)
    else:
        summary = str(content)
    return NodeResult("tech_analysis", content, summary, latency)
