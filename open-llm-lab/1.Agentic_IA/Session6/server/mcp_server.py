from __future__ import annotations

from typing import Any, AsyncContextManager

from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

from .config import AppConfig
from .mt5_bridge import MT5Bridge, MT5BridgeStub
from .orchestrator import evaluate
from .schemas import DeskEvaluateRequest


def create_mcp_server(app: FastAPI, config: AppConfig, bridge: MT5Bridge) -> FastMCP:
    """Create and mount the MCP server under /mcp."""
    stub_bridge = MT5BridgeStub()

    server = FastMCP(
        name="Session6-MCP",
        instructions="Herramientas MCP para consultar el mercado cacheado o gatillar el desk.",
        streamable_http_path="/",
    )

    def _resolve_snapshot(symbol: str, timeframe: str):
        snapshot = bridge.latest(symbol, timeframe)
        if not snapshot:
            snapshot = stub_bridge.latest(symbol, timeframe)
        return snapshot

    def _resolve_history(symbol: str, timeframe: str, bars: int):
        history = bridge.bars(symbol, timeframe, bars)
        if not history:
            history = stub_bridge.bars(symbol, timeframe, bars)
        return history

    def _resolve_bridge_for_eval(symbol: str, timeframe: str) -> MT5Bridge:
        return bridge if bridge.latest(symbol, timeframe) else stub_bridge

    @server.tool(
        name="market.get_latest",
        description="Retorna el último snapshot cacheado (o determinista si no hay datos de MT5).",
    )
    async def market_get_latest(symbol: str = "XAU/USD (broker: GOLD-T)", timeframe: str = "M1") -> Any:
        snapshot = _resolve_snapshot(symbol, timeframe)
        if not snapshot:
            raise RuntimeError("No market data available")
        return snapshot.model_dump()

    @server.tool(
        name="market.get_ohlc",
        description="Devuelve la serie OHLC reciente almacenada en cache.",
    )
    async def market_get_ohlc(
        symbol: str = "XAU/USD (broker: GOLD-T)",
        timeframe: str = "M1",
        bars: int = 100,
    ) -> Any:
        return [snap.model_dump() for snap in _resolve_history(symbol, timeframe, bars)]

    @server.tool(
        name="desk.evaluate",
        description="Ejecuta el pipeline LangGraph y retorna la respuesta estructurada del desk.",
    )
    async def desk_eval(
        symbol: str = "XAU/USD (broker: GOLD-T)",
        timeframe: str = "M1",
        notes: str | None = None,
    ) -> Any:
        request = DeskEvaluateRequest(symbol=symbol, timeframe=timeframe, notes=notes)
        active_bridge = _resolve_bridge_for_eval(symbol, timeframe)
        return evaluate(config, active_bridge, request).model_dump()

    mcp_app = server.streamable_http_app()
    app.mount("/mcp", mcp_app)

    lifespan_cm: AsyncContextManager[Any] | None = None

    @app.on_event("startup")
    async def _start_mcp_server() -> None:
        nonlocal lifespan_cm
        lifespan_cm = mcp_app.router.lifespan_context(mcp_app)
        await lifespan_cm.__aenter__()

    @app.on_event("shutdown")
    async def _stop_mcp_server() -> None:
        nonlocal lifespan_cm
        if lifespan_cm is not None:
            await lifespan_cm.__aexit__(None, None, None)
            lifespan_cm = None

    return server
