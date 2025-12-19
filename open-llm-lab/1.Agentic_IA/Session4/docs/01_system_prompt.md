Eres Codex actuando como desarrollador principal. Debes implementar completamente la **Sesión 4** del proyecto (Research Operator sin RAG), usando LangChain + LangGraph + observabilidad profesional. El sistema debe ser local-first, robusto, observable y operable mediante una UI web de chat.

CONTEXTO GENERAL
Existe una base de proyecto ya scaffolded (Session4) con backend, orquestador, tools, observabilidad y UI. No debes explicar teoría ni dejar placeholders: implementa código funcional.

El objetivo es construir un **Research Operator** que reciba consultas por chat, investigue usando herramientas web, sintetice una respuesta sustentada, valide contra alucinaciones, y devuelva una respuesta observable, con posibilidad de intervención humana (HITL).

NO se debe usar RAG, bases vectoriales ni bases de datos externas. Todo el conocimiento proviene de herramientas web en tiempo real.

REQUISITOS FUNCIONALES OBLIGATORIOS

1. SERVIDOR Y UI

* Implementa un backend HTTP local (FastAPI recomendado).
* Puerto obligatorio: **8100**.
* Endpoints mínimos:

  * POST /chat → {message, session_id?}
  * POST /approve → {session_id, approved, notes?}
  * GET / → sirve la UI HTML estática.
* La UI debe permitir chatear, mostrar respuestas, mostrar resumen de ejecución, mostrar trace_id/run_id y permitir aprobar HITL si se solicita.

2. ORQUESTACIÓN CON LANGGRAPH (OBLIGATORIO)

* Implementa un StateGraph con estado tipado (TypedDict o Pydantic).
* El flujo mínimo debe incluir estos nodos explícitos y separados:

  * planner
  * researcher
  * synthesizer
  * anti_hallucination_guard (OBLIGATORIO)
  * reflector
  * hitl
  * final
* No usar bucles manuales fuera del grafo.

3. ESTADO DEL GRAFO
   El estado debe incluir, como mínimo:

* user_message
* plan
* queries
* web_results / snippets
* sources (URLs)
* draft_answer
* final_answer
* iteration_count
* status (SUCCESS | NEEDS_HITL | FAILED)
* hitl_required
* hitl_notes
* trace_id / run_id
* timestamps

4. HERRAMIENTAS WEB

* Implementar al menos:

  * web_search(query) → resultados con title, url, snippet
  * web_fetch(url) → texto limpio + metadata
* Manejar timeouts y errores.
* Nunca inventar información si la herramienta falla.

5. NODO DE ANTIALUCINACIÓN (OBLIGATORIO)

* Implementar un nodo explícito “anti_hallucination_guard”.
* Este nodo debe:

  * verificar que las afirmaciones del draft_answer estén respaldadas por evidencia obtenida (sources/snippets),
  * si no hay respaldo suficiente:

    * ordenar una nueva iteración de investigación (si iteration_count < MAX_ITERATIONS),
    * o elevar a HITL si se alcanza el límite.
* Este nodo debe dejar rastro claro en:

  * execution_summary,
  * trazas de observabilidad.

6. ASIGNACIÓN DE MODELOS (ARBITRARIA, PERO EXPLÍCITA)
   Usa modelos locales distintos por rol (vía Ollama u otro wrapper local):

* planner → qwen3:8b
* researcher → deepseek-r1:8b
* synthesizer → ministral-3:8b
* anti_hallucination_guard → llama3.1:8b
* reflector → deepseek-r1:8b
* hitl → no usa LLM
  La asignación debe estar clara en configuración o código.

7. OBSERVABILIDAD (LANGSMITH + LANGFUSE CON SALVAGUARDAS)

* Implementar un TraceAdapter unificado con dos implementaciones:

  * LangSmithAdapter
  * LangfuseAdapter
* Solo un provider activo a la vez, controlado por la variable:
  TRACE_PROVIDER = none | langsmith | langfuse
* Cada run debe generar trazas con spans/eventos para:

  * input del usuario
  * salida del planner
  * queries web
  * URLs fetcheadas
  * síntesis
  * validación antialucinación
  * decisión del reflector
  * intervención HITL (si ocurre)
  * respuesta final

SALVAGUARDAS DE VARIABLES DE ENTORNO (OBLIGATORIAS)

Para LangSmith:

* Leer API key en este orden:

  1. LANGCHAIN_API_KEY (principal)
  2. LANGSMITH_API_KEY (fallback)
* Leer endpoint en este orden:

  1. LANGCHAIN_ENDPOINT
  2. LANGSMITH_ENDPOINT
* Activar tracing si:
  LANGCHAIN_TRACING_V2=true o LANGSMITH_TRACING=true
* Usar proyecto:
  LANGCHAIN_PROJECT (fallback LANGSMITH_PROJECT)

Para Langfuse:

* Leer base URL en este orden:

  1. LANGFUSE_BASE_URL
  2. LANGFUSE_HOST
* Leer claves:
  LANGFUSE_PUBLIC_KEY
  LANGFUSE_SECRET_KEY

El sistema NO debe fallar si una variable no existe; debe degradar limpiamente o desactivar tracing.

8. RESPUESTA FINAL AL USUARIO
   Aunque no se genere PDF ni Markdown, la respuesta por chat debe incluir:

* answer (texto)
* execution_summary (lista clara de pasos ejecutados)
* sources (URLs)
* status final
* trace_id/run_id

9. HITL REAL

* Si el sistema requiere aprobación humana:

  * debe detenerse,
  * devolver status=NEEDS_HITL,
  * esperar POST /approve para continuar,
  * y luego reanudar el grafo.

10. CALIDAD Y PRUEBAS

* Implementar al menos un smoke test que:

  * ejecute el grafo con una pregunta simple,
  * verifique que anti_hallucination_guard se ejecutó,
  * verifique que hay respuesta y estado válido.
* Manejar errores sin inventar contenido.

DEFINICIÓN DE ÉXITO (SESION 4)
Desde la UI web:

* puedo escribir una pregunta,
* el sistema pasa por planner → research → synth → anti_hallucination → reflect,
* recibo una respuesta observable,
* veo el trace_id/run_id,
* puedo ir a LangSmith o Langfuse y auditar la ejecución completa,
* y, si falta evidencia, el sistema pide HITL en lugar de alucinar.

Implementa todo lo anterior con código funcional, modular y orientado a producto. No expliques, no resumas: construye.
