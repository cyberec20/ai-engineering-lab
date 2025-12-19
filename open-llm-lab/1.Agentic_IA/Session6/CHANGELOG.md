# Changelog

## 0.1.2 - 2025-12-18
- README actualizado: documentación del flujo MCP (endpoint `/mcp`, uso en el inspector y tokens del proxy), aclaraciones sobre `ENABLE_GATING`, `DEBUG_INTERNAL` y scripts `.bat`.
- Sin cambios de código; sólo documentación y guías.

## 0.1.1 - 2025-12-18
- `/mcp` convertido en endpoint MCP real (FastMCP streamable-http) con tools `market.get_latest`, `market.get_ohlc` y `desk.evaluate`.
- API REST preservada bajo `/api/**`; la UI sigue consumiendo únicamente REST.
- Fallback determinista para MCP: si no hay ticks de MT5 se usan snapshots del stub para responder y correr `desk.evaluate`.
- Scripts y documentación del MCP Inspector actualizados (transport streamable-http, token del proxy y URL del proxy documentados).
- Smoke tests cubren handshake MCP + llamada a `desk.evaluate`.

## 0.1.0 - 2025-12-18
- Integración MT5 -> FastAPI via `/mt5/push` con token compartido y cacheo de snapshots.
- Pipeline LangGraph con nodos `market_reader`, `tech_analysis`, `risk_guard`, `final_decider`, `explainer` + trazas nativas (LangSmith / Langfuse).
- Gating configurable (`ENABLE_GATING`, `GATE_*`) y cache de decisiones por vela.
- Risk guard determinístico (spread / range / body / delta) + warnings cuando el gating está desactivado.
- MCP server inicial + scripts `.bat` para run / reset / smoke / inspector y documentación base.
