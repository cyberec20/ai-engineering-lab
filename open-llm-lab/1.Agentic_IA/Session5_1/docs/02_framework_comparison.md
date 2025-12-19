# Análisis Comparativo: Multi-Modelo en Session 4, 5 y 5.1

## Resumen Ejecutivo

**✅ SÍ, todas las sesiones implementaron multi-modelo**, pero con niveles de complejidad muy diferentes:

| Framework | Multi-Modelo | Complejidad | Estabilidad | Recomendación |
|-----------|--------------|-------------|-------------|---------------|
| **Session 4** (LangGraph) | ✅ Sí | 🟢 Baja | 🟢 Alta | ⭐ **Recomendado** |
| **Session 5** (AutoGen-style) | ✅ Sí | 🟡 Media | 🟢 Alta | ⭐ **Recomendado** |
| **Session 5.1** (CrewAI) | ✅ Sí | 🔴 Alta | 🔴 Baja | ⚠️ **No recomendado** |

---

## 1. Session 4 (LangGraph) - Multi-Modelo ✅

### Implementación
```python
# app/orchestrator/llms/router.py
class LLMRouter:
    def __init__(self, config: AppConfig, available_models: set[str] | None = None):
        models = RoleModels(
            planner=_choose_model(config.model_planner, available_models),
            researcher=_choose_model(config.model_researcher, available_models),
            synthesizer=_choose_model(config.model_synthesizer, available_models),
            guard=_choose_model(config.model_guard, available_models),
            reflector=_choose_model(config.model_reflector, available_models),
        )
```

### Configuración (.env)
```env
# Implícito - usa fallbacks inteligentes
FALLBACK_MODELS = ["llama3.1:8b", "qwen2.5:7b", "llama3:8b", "mistral:7b"]
```

### Ventajas
- ✅ **Muy simple**: Un solo `LLMRouter` centralizado
- ✅ **Fallbacks automáticos**: Si un modelo no está disponible, usa el siguiente
- ✅ **Sin configuración explícita**: Funciona out-of-the-box
- ✅ **Estable**: LangGraph es maduro y bien documentado

### Desventajas
- ⚠️ Menos control granular por agente (pero esto es raramente necesario)

---

## 2. Session 5 (AutoGen-style) - Multi-Modelo ✅

### Implementación
```python
# Configuración explícita por agente en .env
MODEL_RESEARCH_LEAD=qwen3:8b
MODEL_WEB_RESEARCHER=deepseek-r1:8b  # (ahora qwen2.5:7b)
MODEL_FACT_CHECKER=llama3.1:8b
MODEL_SYNTHESIZER=ministral-3:8b
MODEL_CRITIC=llama3.1:8b
MODEL_FORMATTER=qwen2.5:7b
```

### Uso
```python
# app/orchestrator/query_interpreter.py
llm = ChatOllama(
    model=self._config.model_research_lead,  # qwen3:8b
    base_url=self._config.ollama_base_url,
    temperature=0
)
```

### Ventajas
- ✅ **Control total**: Cada agente tiene su modelo específico
- ✅ **Configuración clara**: Fácil de entender y modificar en `.env`
- ✅ **Sin dependencias pesadas**: Solo usa `ChatOllama` de LangChain
- ✅ **Estable**: Implementación directa sin abstracciones complejas

### Desventajas
- ⚠️ Requiere configuración manual (pero es simple)

---

## 3. Session 5.1 (CrewAI) - Multi-Modelo ✅ (pero problemático)

### Implementación
```python
# app/orchestrator/crew_factory.py
def _make_llm(model_name: str, config: AppConfig):
    return LLM(
        model=f"ollama/{model_name}",
        base_url=config.ollama_base_url,
        api_base=config.ollama_base_url,
        timeout=config.request_timeout_seconds,
        num_retries=1,
    )
```

### Configuración
```yaml
# app/orchestrator/crew_config/agents.yaml
WebResearcher:
  role: WebResearcher
  model: qwen2.5:7b  # Hardcoded aquí
  tools: [web_search, web_fetch]
```

**Y también en** `app/core/config.py`:
```python
MODEL_WEB_RESEARCHER: str = os.getenv("MODEL_WEB_RESEARCHER", "qwen2.5:7b")
```

### Problemas Encontrados

#### 🔴 **Problema 1: Configuración Duplicada**
- Modelos definidos en **3 lugares**: `.env`, `agents.yaml`, `config.py`
- Cambiar un modelo requiere editar múltiples archivos
- Alto riesgo de inconsistencias (como vimos con `deepseek-r1:8b`)

#### 🔴 **Problema 2: Parsing JSON Frágil**
- CrewAI devuelve JSON envuelto en markdown code blocks
- Caracteres de control inválidos en strings
- Requiere sanitización manual con `strict=False`
- WebResearcher devuelve listas en lugar de dicts

#### 🔴 **Problema 3: Debugging Complejo**
- Errores ocultos en capas de abstracción
- Logs verbosos pero poco útiles
- Difícil identificar dónde falla exactamente

#### 🔴 **Problema 4: Overhead de CrewAI**
- Telemetry warnings en Windows
- Múltiples capas de abstracción (LiteLLM → CrewAI → Ollama)
- Más lento que implementaciones directas

---

## Comparación de Complejidad

### Cambiar un Modelo

**Session 4 (LangGraph)**:
```bash
# Automático - usa fallbacks
# O editar config.py si quieres control
```

**Session 5 (AutoGen)**:
```env
# .env
MODEL_WEB_RESEARCHER=llama3.1:8b
```
✅ **1 línea, 1 archivo**

**Session 5.1 (CrewAI)**:
```yaml
# 1. agents.yaml
WebResearcher:
  model: llama3.1:8b
```
```python
# 2. config.py
MODEL_WEB_RESEARCHER: str = os.getenv("MODEL_WEB_RESEARCHER", "llama3.1:8b")
```
```env
# 3. .env
MODEL_WEB_RESEARCHER=llama3.1:8b
```
❌ **3 archivos diferentes**

---

## Recomendaciones

### ⭐ **Para Producción: Session 4 (LangGraph)**
**Razones**:
- Framework maduro y estable
- Excelente para workflows complejos
- Fallbacks automáticos
- Debugging más simple
- Comunidad grande

**Cuándo usar**:
- Necesitas workflows con ramificaciones condicionales
- Quieres observabilidad nativa (LangSmith)
- Prefieres estabilidad sobre flexibilidad

---

### ⭐ **Para Prototipado Rápido: Session 5 (AutoGen-style)**
**Razones**:
- Implementación más simple
- Control total sin overhead
- Configuración clara y explícita
- Fácil de entender y modificar
- Sin dependencias pesadas

**Cuándo usar**:
- Necesitas control fino por agente
- Quieres código minimalista
- Prefieres flexibilidad sobre abstracciones

---

### ⚠️ **Evitar: Session 5.1 (CrewAI)**
**Razones**:
- Configuración fragmentada (3 lugares)
- Parsing JSON frágil
- Debugging complejo
- Overhead innecesario
- Menos maduro que LangGraph

**Problemas específicos**:
1. Hardcoded models en YAML sobrescriben `.env`
2. JSON con caracteres de control inválidos
3. Respuestas inconsistentes (lista vs dict)
4. Telemetry warnings en Windows
5. Múltiples capas de abstracción

---

## Conclusión

**✅ Sí, Session 4 y Session 5 implementaron multi-modelo exitosamente y fueron más fáciles que CrewAI.**

### Ranking Final

1. **🥇 Session 5 (AutoGen-style)** - Mejor balance simplicidad/control
2. **🥈 Session 4 (LangGraph)** - Mejor para workflows complejos
3. **🥉 Session 5.1 (CrewAI)** - Demasiado complejo para el beneficio

### Próximos Pasos Recomendados

Si quieres continuar con multi-modelo:
1. **Migrar a Session 5 (AutoGen-style)** - Más simple y directo
2. **O usar Session 4 (LangGraph)** - Si necesitas workflows complejos
3. **Abandonar CrewAI** - No aporta valor suficiente vs complejidad

---

## Evidencia de Multi-Modelo

### Session 4
```python
# 5 modelos diferentes por rol
planner: str
researcher: str
synthesizer: str
guard: str
reflector: str
```

### Session 5
```env
# 6 modelos configurables
MODEL_RESEARCH_LEAD=qwen3:8b
MODEL_WEB_RESEARCHER=qwen2.5:7b
MODEL_FACT_CHECKER=llama3.1:8b
MODEL_SYNTHESIZER=ministral-3:8b
MODEL_CRITIC=llama3.1:8b
MODEL_FORMATTER=qwen2.5:7b
```

### Session 5.1 (CrewAI)
```yaml
# 5 agentes con modelos diferentes
ResearchLead: qwen3:8b
WebResearcher: qwen2.5:7b
FactChecker: llama3.1:8b
Synthesizer: ministral-3:8b
Critic: llama3.1:8b
```

**Todos implementan multi-modelo**, pero Session 5 y Session 4 lo hacen de forma mucho más elegante y mantenible.
