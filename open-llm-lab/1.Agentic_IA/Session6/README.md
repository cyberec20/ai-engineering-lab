# Session6 - MCP Trading Desk

Ejercicio que conecta MetaTrader 5 con un pipeline multi-modelo (LangGraph), un servidor MCP (FastMCP) y observabilidad (LangSmith / Langfuse). MT5 empuja snapshots, se cachean y la UI permite gatillar evaluaciones bajo demanda.

## Arquitectura

- **Ingesta**: `scripts/EA/S6_MCP_PushEA.mq5` envia velas + bid/ask firmados con `MT5_SHARED_SECRET`.
- **Bridge**: `server/mt5_bridge.py` guarda las ultimas velas por simbolo / timeframe (o usa `MT5BridgeStub` cuando `DEBUG_INTERNAL=1` y se habilita el stub en las pruebas).
- **API vs MCP**:
  - Rutas `/api/**` (y `/mt5/push`) son REST normales. La UI solo habla con estas rutas.
  - `/mcp` es el endpoint FastMCP (transport **streamable-http**) y no aparece en `/docs` porque no forma parte del OpenAPI. El MCP Inspector u otros clientes deben apuntar alli.
- **Pipeline LangGraph**:
  1. `market_reader` (`MODEL_MARKET_READER`).
  2. `tech_analysis` (`MODEL_TECH_ANALYSIS`).
  3. `risk_guard` (gating deterministico).
  4. `final_decider`.
  5. `explainer`.
- **Gating / Cache**:
  - `ENABLE_GATING=1` aplica umbrales (`GATE_*`) antes de correr modelos costosos. `ENABLE_GATING=0` desactiva los filtros.
  - `DECISION_CACHE_LIMIT` reutiliza respuestas por vela (`symbol|tf|ts`).
- **Observabilidad**: `TRACING_BACKEND=langsmith|langfuse|both|none` y aliases `LANGCHAIN_*` automaticos.

## Setup

1. Copia `.env.example` a `.env` y completa:
   - Claves LangSmith / Langfuse.
   - `MODEL_*` segun modelos locales.
   - `MT5_SHARED_SECRET`, `HOST`, `PORT`.
   - `ENABLE_GATING` y `GATE_*` para ajustar umbrales.
   - `DEBUG_INTERNAL=1` anade logs por nodo y habilita el stub (util cuando no llegan ticks reales).
2. Activar `.venv` compartido e instalar dependencias:
   ```bash
   pip install -r requirements.session6.txt
   ```
3. Modelos locales:
   - Los `*_BASE_URL` permiten usar Ollama o LM Studio (HTTP), segun tu setup.

## Docs
- docs/01_system_prompt.md
- docs/02_mcp_server.md
- docs/03_improvements.md
## Ejecucion
```bat
scripts\S6_Run_Server.bat
```

El script imprime diagnostico, limpia el puerto y lanza Uvicorn.
- UI: `http://HOST:PORT/`
- Swagger REST: `http://HOST:PORT/docs`
- MCP Inspector (opcional): `scripts\S6_MCP_Inspector.bat`

## Smoke tests

```bat
scripts\S6_Smoke_Tests.bat
```

Ejecuta `pytest` con snapshots stub y valida `/health`, `/api/desk/evaluate` y la tool MCP `desk.evaluate`.

## MCP Inspector

```bat
scripts\S6_MCP_Inspector.bat
```

El script:
1. Reescribe `scripts\mcp-inspector.json` con `HOST`/`PORT`.
2. Lanza `npx @modelcontextprotocol/inspector --config ... --server local-mt5`.
3. Imprime:
   - URL del proxy (`http://127.0.0.1:6277/mcp`).
   - Token del proxy (ya incluido en el link sugerido).

En la UI del inspector:
1. Transport = **Streamable HTTP**.
2. URL = `http://127.0.0.1:6277/mcp`.
3. Header name = `MCP-Inspector-Auth`.
4. Bearer token / Proxy session token = token mostrado en la consola (o abre el link sugerido que ya lo incluye).
5. Conectar. Las tools expuestas (`market.get_latest`, `market.get_ohlc`, `desk.evaluate`) deberian estar disponibles.

## Reset limpio

```bat
scripts\S6_Reset_Local.bat
```

Elimina logs, artefactos y cache temporal.

