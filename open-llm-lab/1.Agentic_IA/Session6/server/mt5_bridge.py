from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, Tuple

from .schemas import MarketSnapshot, PushPayload

logger = logging.getLogger(__name__)


class MT5Bridge:
    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, str], Deque[MarketSnapshot]] = {}

    def push(self, payload: PushPayload) -> None:
        key = (payload.symbol, payload.timeframe)
        queue = self._cache.setdefault(key, deque(maxlen=500))
        snapshot = MarketSnapshot(
            symbol=payload.symbol,
            timeframe=payload.timeframe,
            bid=payload.bid,
            ask=payload.ask,
            ohlc=payload.ohlc,
            ts=payload.ts,
        )
        queue.appendleft(snapshot)
        logger.info("mt5_push", extra={"event": "mt5_push", "symbol": payload.symbol})

    def latest(self, symbol: str, timeframe: str) -> MarketSnapshot | None:
        queue = self._cache.get((symbol, timeframe))
        if queue:
            return queue[0]
        return None

    def bars(self, symbol: str, timeframe: str, limit: int) -> list[MarketSnapshot]:
        queue = self._cache.get((symbol, timeframe))
        if not queue:
            return []
        return list(list(queue)[:limit])


class MT5BridgeStub(MT5Bridge):
    def __init__(self) -> None:
        super().__init__()
        now = datetime.now(timezone.utc)
        for i in range(200):
            payload = PushPayload(
                source="stub",
                symbol="XAU/USD (broker: GOLD-T)",
                timeframe="M1",
                ts=now,
                bid=2350 + i * 0.05,
                ask=2350.2 + i * 0.05,
                ohlc={"open": 2350, "high": 2351, "low": 2349, "close": 2350.5},
            )
            super().push(payload)
