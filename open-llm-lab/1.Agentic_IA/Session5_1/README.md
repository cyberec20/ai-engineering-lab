# Session 5.1 - Research Operator (CrewAI)

Este ejercicio replica el objetivo de `Session4` / `Session5` (Research Operator sin RAG) pero cambia la orquestacion: aqui se usa CrewAI (crew + tasks) con contratos JSON estrictos entre pasos.

## Que incluye
- FastAPI (`GET /`, `GET /static/...`, `GET /health`, `POST /chat`).
- UI web en `app/ui/static` (en esta carpeta ya existe; se reutiliza y se ajusta a "Session5.1").
- Web tools (`web_search`, `web_fetch`) con `WEB_PROVIDER=live|stub`.
- Observabilidad intercambiable por `.env`: `TRACE_PROVIDER=none|langsmith|langfuse`.
- Scripts Windows `.bat` para levantar servidor y correr smoke tests.
- Smoke tests deterministas (sin red externa) usando `WEB_PROVIDER=stub`.

## Ejecutar
- Copia `.env.example` a `.env` y completa placeholders.
- Servidor: `Session5_1\scripts\run_dev.bat`
- Tests: `Session5_1\scripts\run_tests.bat`

## Archivos clave
- `docs/01_system_prompt.md` (requisitos del ejercicio)
- `CHANGELOG.md` (cambios recientes)
- `app/orchestrator/crew_config/*.yaml` (roles, tasks y tools)
- Comparativa: `docs/02_framework_comparison.md`

## Docs
- docs/01_system_prompt.md
- docs/02_framework_comparison.md
## Limitaciones encontradas con CrewAI
### Problemas criticos
1. JSON parsing fragil
   - Agents devuelven JSON envuelto en markdown code blocks
   - JSON con caracteres de control invalidos
   - Delimitadores malformados
   - Requiere sanitizacion manual con `strict=False` y extraccion de code blocks

2. Configuracion fragmentada
   - Modelos definidos en 3 lugares: `.env`, `agents.yaml`, `config.py`
   - Valores hardcoded en YAML sobrescriben variables de entorno
   - Alto riesgo de inconsistencias

3. Respuestas inconsistentes
   - WebResearcher devuelve lista `[...]` en lugar de dict `{"evidence": [...]}`
   - Requiere wrapping manual para validacion Pydantic
   - Diferentes agentes usan formatos diferentes

4. Debugging complejo
   - Multiples capas de abstraccion (LiteLLM -> CrewAI -> Ollama)
   - Errores ocultos en capas intermedias
   - Logs verbosos pero poco utiles para identificar root cause

5. Overhead innecesario
   - Telemetry warnings en Windows (`signal only works in main thread`)
   - Mas lento que implementaciones directas
   - Mayor complejidad sin beneficios claros

### Estado actual
- Funciona: todos los agentes ejecutan correctamente (planning, web_research, fact_check, synthesis, critic)
- Fuentes: recupera URLs correctas de Wikipedia
- UI: no muestra respuesta final debido a JSON parsing errors
- Produccion: no recomendado para uso real

## Comparacion con Session 4 y Session 5

| Framework | Multi-Modelo | Complejidad Config | Estabilidad | Recomendacion |
|-----------|--------------|-------------------|-------------|---------------|
| Session 4 (LangGraph) | 5 modelos | Baja (fallbacks auto) | Alta | Recomendado |
| Session 5 (AutoGen) | 6 modelos | Baja (1 linea .env) | Alta | Recomendado |
| Session 5.1 (CrewAI) | 5 modelos | Alta (3 archivos) | Baja | No recomendado |

### Conclusion
CrewAI requiere mayor configuracion y manejo especial para pasar informacion correctamente entre miembros del equipo. Los problemas de JSON parsing y configuracion fragmentada lo hacen menos practico que LangGraph (Session 4) o AutoGen-style (Session 5) para proyectos reales.

Recomendacion: usar Session 5 (AutoGen-style) para simplicidad o Session 4 (LangGraph) para workflows complejos.

## Notas importantes (Session 4/5)
- Queries web deben ser keywords (no preguntas largas).
- Respuesta final siempre en el idioma del usuario (detectar idioma; forzar solo al final).
- Observabilidad debe ser util:
  - cada step debe adjuntar `output` no vacio (evita `Raw Output: null`),
  - evitar runs raiz duplicados por auto-tracing mal configurado.

## Futuro (no parte del ejercicio 5.1)
### CrewAI + LangGraph (modo hibrido)
No son herramientas mutuamente excluyentes. En un proyecto real puedes:
- usar LangGraph como orquestador externo (estado, routing, HITL, budgets),
- ejecutar CrewAI como submodulo para la etapa multi-agente.

Para el ejercicio 5.1 se mantiene solo CrewAI para reducir complejidad y aislar el aprendizaje.


