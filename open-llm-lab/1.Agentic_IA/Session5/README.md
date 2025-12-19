# Session 5 - Research Operator (AutoGen-style, equipo autogenerado)

Este ejercicio replica el objetivo de `Session4` (Research Operator sin RAG) pero cambia la orquestacion: aqui el sistema crea dinamicamente un equipo de agentes conversacionales y gestiona turn-taking + criterios de finalizacion (AutoGen-style), sin usar LangGraph.

La UI puede ser reutilizada (copiada) desde `Session4` para acelerar. En este repo ya existe una base en `app/ui/static`.

## Preflight (antes de correr)
- Estas en `C:\IA_Local\scripts\Agentic_AI\Session5`.
- Estas usando el Python del venv: `..\.venv\Scripts\python.exe` (no el global).
- Puerto `8100` libre.
- Si vas a usar Langfuse self-host: Docker Desktop o Engine running y puerto `3000` libre.
- Si habilitas nodos LLM: Ollama corriendo y el modelo existe (`ollama list`).
- Copia `.env.example` a `.env` y completa placeholders.
- `.env` sin espacios alrededor de `=` (ej.: `KEY=value`, no `KEY = value`).

## Que debe quedar implementado (minimo)

### Backend (FastAPI)
- `GET /` sirve la UI (index.html).
- `GET /static/...` sirve assets.
- `POST /chat` contrato estable:
  ```json
  {
    "answer": "...",
    "sources": ["https://..."],
    "agents_created": [{"role":"...", "model":"..."}],
    "models_used": ["..."],
    "execution_summary": {"turns": 0, "decisions": [], "fallbacks": []},
    "trace_id": "...",
    "status": "SUCCESS | INSUFFICIENT_EVIDENCE | FAILED"
  }
  ```
- `GET /health` devuelve 200 (usado por smoke tests).

### Orquestacion (AutoGen-style)
- `QueryInterpreter` (LLM + fallback minimo) para extraer intencion/entidades/keywords sin regex.
- `AgentCreator` para definir roles/tools/modelo por agente.
- `MultiAgentEngine` con budgets estrictos, turn-taking y TTL por `session_id`.
- Web tools: `web_search` + `web_fetch` con timeouts, dedupe, limpieza, caching por sesion y manejo 403/429/CAPTCHA.

## UI (reutilizable)
Ruta actual: `app/ui/static`.

Regla: si la UI es copiada desde `Session4`, se reutiliza la misma estructura y solo se ajusta:
- titulos/labels (`Session5`),
- campos de respuesta (`agents_created`, `models_used`, `execution_summary`, `trace_id`),
- y un panel visible de `session_id`.

## Observabilidad (switch nativo)
El ejercicio debe permitir alternar sin tocar codigo, solo editando `.env`:
- `TRACE_PROVIDER=none`
- `TRACE_PROVIDER=langsmith`
- `TRACE_PROVIDER=langfuse`

### Plantillas minimas `.env` (placeholders)
**none**
```env
TRACE_PROVIDER=none
LANGCHAIN_TRACING_V2=false
```

**langsmith (nativo)**
```env
TRACE_PROVIDER=langsmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=sk-PASTE_HERE
LANGCHAIN_PROJECT=Session5-ResearchOperator-AutoGen
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

**langfuse (nativo)**
```env
TRACE_PROVIDER=langfuse
LANGFUSE_BASE_URL=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-PASTE_HERE
LANGFUSE_SECRET_KEY=sk-lf-PASTE_HERE
```

Checklist de cierre (lo que debe verse en la UI del provider):
- `langsmith`: run con start/end (no "pending"), spans para tools y etapas/agentes.
- `langfuse`: traza con grafo/timeline visible y start/end definidos (no "pending").

Nota sobre duplicados en LangSmith:
- Si activas `LANGCHAIN_TRACING_V2=true`, LangChain puede crear runs raiz adicionales por cada llamada LLM (por ejemplo `ChatOllama`).
- En Session5 evitamos eso para que cada consulta sea 1 solo root run (`research_operator`) con spans internos; por eso `LANGCHAIN_TRACING_V2` queda en `false` y el tracing se controla desde `TRACE_PROVIDER=langsmith`.

## Scripts
- `scripts/run_dev.bat`: levanta Uvicorn en `8100` usando el python del venv.
- `scripts/run_tests.bat`: ejecuta `pytest -q` con `PYTHONPATH` seteado.

## Smoke tests (obligatorios)
El proyecto incluye `tests/test_smoke.py` que valida "hay vida" sin depender de red externa:
- Forzar `TRACE_PROVIDER=none`.
- Forzar `WEB_PROVIDER=stub` (o equivalente) para resultados deterministas.
- Validar `GET /health` y que `POST /chat` responde el contrato (aunque sea `INSUFFICIENT_EVIDENCE`).

## Material de estudio
- `docs/01_system_prompt.md` (requisitos completos del ejercicio)
- `Session5_ResearchOperator_AutoGen.html` (guia visual)
- `CHANGELOG.md` (cambios recientes)

