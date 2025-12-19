from __future__ import annotations

import json

from ..llm_client import LLMClient
from .base import NodeResult, invoke_json


def run_market_reader(llm: LLMClient, model: str, snapshot) -> NodeResult:
    variables = {
        "symbol": snapshot.symbol,
        "timeframe": snapshot.timeframe,
        "bid": snapshot.bid,
        "ask": snapshot.ask,
        "ohlc": snapshot.ohlc,
    }
    content, latency = invoke_json(llm, model, "market_reader", variables)
    if isinstance(content, dict):
        insight = content.get("insight")
        if isinstance(insight, str):
            summary = insight
        else:
            summary = json.dumps(insight or content)[0:200]
    else:
        summary = str(content)
    return NodeResult("market_reader", content, summary, latency)
