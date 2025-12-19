from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MarketSnapshot(BaseModel):
    symbol: str
    timeframe: str
    bid: float
    ask: float
    ohlc: dict[str, float]
    ts: datetime


class DeskEvaluateRequest(BaseModel):
    symbol: str = Field(default="XAU/USD (broker: GOLD-T)")
    timeframe: str = Field(default="M1")
    notes: str | None = None


class NodeOutput(BaseModel):
    name: str
    model: str
    latency_ms: int
    summary: str | None = None
    raw: Any | None = None


class DeskEvaluateResponse(BaseModel):
    decision: str
    reasons: list[str]
    market_snapshot: MarketSnapshot | None
    node_outputs: list[NodeOutput]
    meta: dict[str, Any]


class PushPayload(BaseModel):
    source: str
    symbol: str
    timeframe: str
    ts: datetime
    bid: float
    ask: float
    ohlc: dict[str, float]
