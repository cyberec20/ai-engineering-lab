# Session 3 ? Crew de agentes para stock picker + SDR

## Objetivo
Extender el agente SDR de Session 2 con un crew multi-modelo para un flujo educativo de analisis de acciones, manteniendo todo local con Ollama.

## Que hay en esta sesion
- `main.py`: API FastAPI que combina SDR (Session 2) con el crew de acciones (Session 3).
- `llm_client_local.py`: cliente para llamar a Ollama via `/api/chat`.
- `agents/`: runtime SDR (Agent, ToolRouter, AgentRunner, tools).
- `crew/stock_picker.py`: pipeline Researcher -> Analyst -> Writer -> Judge.
- `sdr_chat.html`: UI de chat con comando `/stocks`.
- `Session3_Crew_Stocks_Roadmap.html`: guia visual de la sesion.

## Arquitectura (resumen)
- **SDR**: mismo flujo de Session 2 (fetch_html, generate_email_draft, etc.).
- **Crew stock picker**:
  - Researcher (qwen3:8b) obtiene contexto con `yfinance`.
  - Analyst (deepseek-r1:8b) resume pros, contras y riesgos.
  - Writer (llama3.1:8b) redacta el informe legible.
  - Judge (qwen2.5:7b) ajusta tono y coherencia final.

## Endpoints
- `GET /` health basico y lista de endpoints.
- `POST /sdr/email` genera un correo SDR (agente efimero).
- `POST /sdr/chat` chat con memoria por `session_id`.
- `GET /sdr/chat-ui` devuelve la UI HTML.
- `POST /crew/stock-picker` endpoint directo para el crew.

## Comando especial en chat
En `/sdr/chat` puedes activar el crew con:
```
/stocks AAPL, NVDA, TSLA
```
Si quieres el detalle por agente, agrega `debug`:
```
/stocks AAPL, NVDA, TSLA debug
```

## Requisitos
- Python 3.11+
- Ollama instalado y corriendo
- Paquetes: `fastapi`, `uvicorn`, `requests`, `httpx`, `pydantic`, `yfinance`

## Como ejecutar
1) Asegura que Ollama esta activo:
```
ollama run qwen2.5:7b
```

2) Instala dependencias:
```
pip install fastapi uvicorn requests httpx pydantic yfinance
```

3) Inicia el servidor:
```
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

4) Abre la UI:
```
http://localhost:8100/sdr/chat-ui
```

## Ejemplo rapido
Request a `/crew/stock-picker`:
```json
{
  "tickers": ["AAPL", "NVDA", "TSLA"],
  "risk_profile": "moderado",
  "horizon": "mediano",
  "debug": true
}
```

## Troubleshooting
- Modelos: si falla un rol, revisa ollama list y descarga el modelo faltante.
- yfinance: si no hay datos, verifica el ticker y la conexion a Internet.
- /stocks: si no responde, confirma que el mensaje empieza con /stocks y que el server esta en 8100.
- Debug: para traza por agente, agrega debug al comando.
## Notas
- El modo SDR sigue activo para mensajes normales; el crew solo se activa con `/stocks`.
- `yfinance` es una fuente ligera; el objetivo es entender el flujo, no dar recomendaciones reales.

