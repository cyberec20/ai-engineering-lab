# Changelog - Session4 (Research Operator)

## 2025-12-15

### Observability / LangSmith (pipeline nativo)
- Cambio: se migró a **tracing nativo** de LangSmith (LangChain/LangGraph) para evitar runs en estado **Pending**.
- Implementación: el servidor inyecta `LangChainTracer` como callback en el `config` de `graph.stream(...)` cuando `TRACE_PROVIDER=langsmith`.
- Estado: validado en UI de LangSmith (runs cierran correctamente).

### Observability / Langfuse (pipeline nativo)
- Cambio: se habilitó **tracing nativo** de Langfuse (LangChain callback handler) cuando `TRACE_PROVIDER=langfuse`.
- Implementación: el servidor inyecta `langfuse.langchain.CallbackHandler` como callback en el `config` de `graph.stream(...)`.
- Estado: Langfuse local levantado y probado; se confirmó que registra trazas y muestra el grafo.

### Deuda técnica (tracing manual)
- `app/orchestrator/observability/langsmith_adapter.py` queda como referencia/debug pero no es confiable: se observó `end_time=None` persistente y/o `409 Conflict: payloads already received` al intentar cerrar runs manualmente.
- Mantener el enfoque “pipeline nativo por proveedor” como baseline; si se re‑intenta manual, hacerlo con una prueba de humo que verifique cierre real del run.

