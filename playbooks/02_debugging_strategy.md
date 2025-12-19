# Estrategia de Debugging Multi-Nivel para Proyectos Multi-Agente

## Introducción

Al trabajar con sistemas multi-agente (LangGraph, AutoGen, CrewAI, etc.), enfrentamos un desafío común: **las herramientas de observabilidad externa (LangSmith, Langfuse) muestran el flujo general, pero no revelan las interacciones internas** dentro de componentes complejos.

Este documento describe una **estrategia de debugging en dos niveles** que combina observabilidad externa con logging interno detallado, aplicable a cualquier framework.

---

## El Problema: Cajas Negras en Observabilidad

### Ejemplo en LangSmith

Cuando ejecutas un workflow multi-agente, LangSmith muestra:

```
research_operator (45s)
  ├─ query_interpreter (10s) ✅ Visible
  ├─ crew_kickoff (30s) ⚠️ CAJA NEGRA
  └─ format_response (5s) ✅ Visible
```

**Problema**: No sabes qué pasa dentro de `crew_kickoff`:
- ¿Qué agentes se ejecutaron?
- ¿Cuánto tardó cada uno?
- ¿Qué herramientas usaron?
- ¿Dónde está el cuello de botella?

---

## La Solución: Debugging en Dos Niveles

### Nivel 1: Observabilidad Externa (LangSmith/Langfuse)
**Propósito**: Vista panorámica del flujo completo

**Qué te da:**
- ✅ Timeline end-to-end
- ✅ Latencias por componente
- ✅ Inputs/outputs de cada paso
- ✅ Métricas agregadas (tokens, costos)
- ✅ Trazabilidad de errores

**Limitación**: No ve dentro de componentes opacos

---

### Nivel 2: Logging Interno Detallado
**Propósito**: Vista microscópica de interacciones internas

**Qué te da:**
- ✅ Paso a paso dentro de cada componente
- ✅ Variables intermedias
- ✅ Decisiones y ramificaciones
- ✅ Debugging granular
- ✅ Identificación exacta de cuellos de botella

**Limitación**: Solo visible en terminal/logs, no en UI

---

## Implementación Práctica

### 1. Configurar Logging Básico

```python
import logging

# En tu main.py o al inicio de tu aplicación
logging.basicConfig(
    level=logging.INFO,  # Cambiar a DEBUG para más detalle
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
```

### 2. Agregar Logs Estratégicos

#### Ejemplo: Nodo de LangGraph

```python
def research_node(state: ResearchState):
    logger.info(f"🔍 Research node started with {len(state['queries'])} queries")
    
    results = []
    for i, query in enumerate(state['queries']):
        logger.info(f"  📝 Processing query {i+1}/{len(state['queries'])}: {query}")
        
        # Web search
        start = time.time()
        search_results = web_search(query)
        duration = time.time() - start
        logger.info(f"    🔎 Search took {duration:.2f}s, got {len(search_results)} results")
        
        # Fetch pages
        for j, url in enumerate(search_results[:3]):
            start = time.time()
            try:
                content = web_fetch(url)
                duration = time.time() - start
                logger.info(f"    📄 Fetched [{j+1}] {url} in {duration:.2f}s, {len(content)} chars")
                results.append(content)
            except Exception as e:
                logger.error(f"    ❌ Failed to fetch {url}: {e}")
    
    logger.info(f"✅ Research node completed with {len(results)} evidence items")
    return {"evidence": results}
```

#### Ejemplo: Agente de CrewAI

```python
# En crew_factory.py
from crewai import Agent, Crew

def build_crew(config, tools):
    # Habilitar verbose mode
    agent = Agent(
        role="WebResearcher",
        verbose=True,  # ← Esto genera logs detallados
        llm=llm,
        tools=tools
    )
    
    crew = Crew(
        agents=[agent],
        tasks=[task],
        verbose=True  # ← Esto también
    )
    
    return crew
```

#### Ejemplo: Función Custom

```python
def synthesize_answer(evidence: list[str], query: str) -> str:
    logger.info(f"🧠 Synthesizing answer from {len(evidence)} evidence items")
    logger.debug(f"  Query: {query}")
    logger.debug(f"  Evidence lengths: {[len(e) for e in evidence]}")
    
    # Preparar prompt
    prompt = build_prompt(evidence, query)
    logger.debug(f"  Prompt length: {len(prompt)} chars")
    
    # Llamar LLM
    start = time.time()
    try:
        response = llm.invoke(prompt)
        duration = time.time() - start
        logger.info(f"  ⚡ LLM call took {duration:.2f}s, response: {len(response)} chars")
        logger.debug(f"  Response preview: {response[:100]}...")
        
        # Validar respuesta
        if not response or len(response) < 50:
            logger.warning(f"  ⚠️ Response seems too short: {len(response)} chars")
        
        return response
        
    except Exception as e:
        logger.error(f"  ❌ LLM call failed: {e}", exc_info=True)
        raise
```

---

### 3. Niveles de Logging

```python
# Producción: solo errores críticos
logging.basicConfig(level=logging.ERROR)

# Desarrollo: info general
logging.basicConfig(level=logging.INFO)

# Debugging profundo: todo
logging.basicConfig(level=logging.DEBUG)
```

**Tip**: Usa variables de entorno para controlar el nivel:

```python
import os

log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(level=getattr(logging, log_level))
```

En `.env`:
```env
LOG_LEVEL=DEBUG  # Para debugging
LOG_LEVEL=INFO   # Para desarrollo
LOG_LEVEL=ERROR  # Para producción
```

---

### 4. Logs Estructurados (Opcional)

Para análisis posterior o integración con sistemas de monitoreo:

```python
import json
import time

def log_event(event_type: str, **kwargs):
    log_entry = {
        "timestamp": time.time(),
        "event": event_type,
        **kwargs
    }
    logger.info(json.dumps(log_entry))

# Uso
log_event("llm_call", 
    model="qwen3:8b", 
    prompt_length=1500, 
    response_length=800,
    duration_ms=2340
)
```

Salida:
```json
{"timestamp": 1702761234.56, "event": "llm_call", "model": "qwen3:8b", "prompt_length": 1500, "response_length": 800, "duration_ms": 2340}
```

---

## Ejemplo Completo: Debugging Session 5.1 (CrewAI)

### Problema Original
- LangSmith mostraba `crew_kickoff: 30s` sin detalles
- No sabíamos qué agente era lento
- No veíamos qué herramientas se usaban

### Solución Implementada

#### 1. Habilitamos verbose en CrewAI
```python
# app/orchestrator/crew_factory.py
Agent(verbose=True, ...)
Crew(verbose=True, ...)
```

#### 2. Agregamos logging en parsing
```python
# app/orchestrator/research_operator.py
def _load_model_output(payload, model_cls):
    logger.info(f"Parsing {model_cls.__name__}, payload type: {type(payload)}")
    
    if isinstance(payload, str):
        logger.info(f"  Starts with backticks: {payload.startswith('```')}")
        # ... extracción de JSON
        logger.info(f"  Extracted JSON length: {len(text)}")
    
    try:
        data = json.loads(text, strict=False)
        logger.info(f"  ✅ Parsed successfully")
        return model_cls.model_validate(data)
    except Exception as e:
        logger.error(f"  ❌ Parsing failed: {e}")
        raise
```

### Resultado en Terminal

```
🚀 Crew: crew
└── 📋 Task: planning
    ├── 🤖 Agent: ResearchLead
    ├── 💭 Thought: I need to create queries...
    └── ✅ Completed (6s)

└── 📋 Task: web_research
    ├── 🤖 Agent: WebResearcher
    ├── 🔧 Used web_search (1.2s)
    ├── 🔧 Used web_fetch (2.3s)
    └── ✅ Completed (8s)

INFO: Parsing WebResearchOutput, payload type: <class 'str'>
INFO:   Starts with backticks: False
INFO:   ✅ Parsed successfully

└── 📋 Task: synthesis
    ├── 🤖 Agent: Synthesizer
    └── ✅ Completed (15s)

INFO: Parsing DraftOutput, payload type: <class 'str'>
INFO:   Starts with backticks: True
INFO:   Extracted JSON length: 5427
ERROR:  ❌ Parsing failed: Expecting ',' delimiter: line 13 column 246
```

**Ahora sabemos exactamente**:
- ✅ Cada agente y su tiempo
- ✅ Qué herramientas se usaron
- ✅ Dónde falló el parsing
- ✅ El error exacto (delimitador faltante)

---

## Mejores Prácticas

### 1. **Logs Concisos pero Informativos**
❌ **Malo**:
```python
logger.info("Processing")
```

✅ **Bueno**:
```python
logger.info(f"Processing query {i+1}/{total}: {query[:50]}...")
```

### 2. **Usa Emojis para Escaneo Rápido**
```python
logger.info("🔍 Starting search")
logger.info("✅ Search completed")
logger.error("❌ Search failed")
logger.warning("⚠️ Partial results")
```

### 3. **Mide Tiempos Críticos**
```python
import time

start = time.time()
result = expensive_operation()
logger.info(f"Operation took {time.time() - start:.2f}s")
```

### 4. **Log Excepciones con Stack Trace**
```python
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)  # ← Incluye stack trace
    raise
```

### 5. **Trunca Datos Largos**
```python
# ❌ Malo: log de 10MB
logger.info(f"Response: {huge_response}")

# ✅ Bueno: log conciso
logger.info(f"Response: {len(huge_response)} chars, preview: {huge_response[:100]}...")
```

---

## Workflow de Debugging Recomendado

### Paso 1: Observabilidad Externa
1. Ejecuta tu workflow con LangSmith/Langfuse habilitado
2. Identifica el componente lento o problemático
3. Anota el tiempo y el contexto

### Paso 2: Logging Interno
1. Habilita `LOG_LEVEL=DEBUG` en `.env`
2. Agrega logs estratégicos en el componente problemático
3. Ejecuta de nuevo y observa la terminal

### Paso 3: Análisis Combinado
1. Compara timeline de LangSmith con logs detallados
2. Identifica el cuello de botella exacto
3. Implementa la solución

### Paso 4: Validación
1. Ejecuta con `LOG_LEVEL=INFO`
2. Verifica que el problema se resolvió en LangSmith
3. Desactiva logs de debugging si no son necesarios

---

## Herramientas Complementarias

### 1. **Rich** (Logs Bonitos en Terminal)
```bash
pip install rich
```

```python
from rich.logging import RichHandler

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[RichHandler(rich_tracebacks=True)]
)
```

### 2. **Loguru** (Logging Simplificado)
```bash
pip install loguru
```

```python
from loguru import logger

logger.info("Simple y poderoso")
logger.debug("Con colores automáticos")
logger.error("Stack traces bonitos")
```

### 3. **Structlog** (Logs Estructurados)
```bash
pip install structlog
```

```python
import structlog

logger = structlog.get_logger()
logger.info("llm_call", model="qwen3:8b", duration=2.3)
```

---

## Conclusión

La combinación de **observabilidad externa + logging interno** te da:

1. **Vista panorámica** (LangSmith/Langfuse) → Qué y cuándo
2. **Vista microscópica** (Logs) → Cómo y por qué
3. **Debugging completo** → Identificación rápida de problemas

Esta estrategia es **universal** y funciona con:
- ✅ LangGraph
- ✅ AutoGen
- ✅ CrewAI
- ✅ Código custom
- ✅ Cualquier framework multi-agente

**Recuerda**: Los logs son tus ojos dentro de las cajas negras. Úsalos estratégicamente y tu debugging será mucho más eficiente.

---

## Referencias

- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [LangSmith Tracing Guide](https://docs.smith.langchain.com/)
- [Rich Library](https://rich.readthedocs.io/)
- [Loguru](https://loguru.readthedocs.io/)
