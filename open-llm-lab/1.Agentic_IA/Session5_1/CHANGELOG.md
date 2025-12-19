# Changelog — Session5_1

## [Unreleased] - 2025-12-16

### Added
- Implementación completa del ejercicio 5.1 (CrewAI): FastAPI + UI, Crew por sesión, YAML de agentes/tareas/tools, web tools `live|stub`, `TRACE_PROVIDER=none|langsmith|langfuse`, scripts `.bat`, y smoke tests.
- Compatibilidad Windows para CrewAI: parcheo de señales faltantes en `signal` antes de importar `crewai`.
- Multi-modelo support: 5 agentes con modelos diferentes (qwen3:8b, qwen2.5:7b, llama3.1:8b, ministral-3:8b).
- Logging detallado para debugging de JSON parsing.

### Issues Encontrados

#### 1. YAML Parsing Error (Resuelto)
- **Problema**: Colons sin escapar en `goal` fields de `agents.yaml`
- **Solución**: Quoted all `goal` and `backstory` values

#### 2. Missing litellm Dependency (Resuelto)
- **Problema**: `"Fallback to LiteLLM is not available"`
- **Solución**: Installed `litellm` package

#### 3. Model Performance Issues (Resuelto)
- **Problema**: `deepseek-r1:8b` causaba timeouts extremos
- **Solución**: Replaced with `qwen2.5:7b` for WebResearcher

#### 4. Hardcoded Models in YAML (Resuelto)
- **Problema**: `deepseek-r1:8b` hardcoded en `agents.yaml` sobrescribía `.env`
- **Solución**: Updated `agents.yaml` y `config.py` fallbacks a `qwen2.5:7b`

#### 5. JSON Parsing Failures (Parcialmente Resuelto)
- **Problema 1**: JSON wrapped in markdown code blocks (` ```json ... ``` `)
  - **Solución**: Added code block extraction logic
- **Problema 2**: Invalid control characters (unescaped newlines)
  - **Solución**: Used `json.loads(text, strict=False)`
- **Problema 3**: WebResearcher returns list instead of dict
  - **Solución**: Auto-wrap lists in `{"evidence": [...]}`
- **Problema 4**: Malformed JSON delimiters (`Expecting ',' delimiter`)
  - **Estado**: **NO RESUELTO** - LLM genera JSON inválido inconsistentemente

### Known Issues

#### Critical
- ❌ **JSON Parsing Still Fails**: A pesar de sanitización, LLMs generan JSON malformado con delimitadores incorrectos
- ❌ **UI No Muestra Respuesta**: `ChatResult.answer` queda vacío debido a parsing errors
- ❌ **Configuración Fragmentada**: Modelos definidos en 3 lugares (`.env`, `agents.yaml`, `config.py`)

#### Non-Critical
- ⚠️ **Telemetry Warnings**: `signal only works in main thread` en Windows (cosmético)
- ⚠️ **Performance**: Más lento que Session 4/5 debido a capas de abstracción

### Conclusiones

**CrewAI no es recomendado para este use case** debido a:
1. JSON parsing frágil e inconsistente
2. Configuración compleja y fragmentada
3. Debugging difícil con múltiples capas de abstracción
4. Overhead innecesario vs Session 4 (LangGraph) o Session 5 (AutoGen-style)

**Alternativas recomendadas**:
- **Session 5 (AutoGen-style)**: Más simple, configuración en 1 archivo
- **Session 4 (LangGraph)**: Más robusto para workflows complejos

Ver `docs/multi_model_comparison.md` para análisis detallado.
