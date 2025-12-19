---

## 1) `web_search / web_fetch`: scraping local (gratis) ✅

**Decisión:** **Scraping local** (sin SerpAPI/Bing/GNews APIs).

**Enfoque recomendado (práctico y estable dentro de lo posible):**

* `web_search`: usar **DuckDuckGo HTML** (endpoint HTML) y parsear resultados con `BeautifulSoup`.
* `web_fetch`: `requests` + parser HTML (BeautifulSoup) con:

  * timeout
  * user-agent realista
  * backoff simple (sleep incremental)
  * límite de resultados (p.ej. top 5)
  * limpieza de texto (quitar nav/footers básicos)

**Tradeoff (aceptado):**

* Puede fallar por rate limits / cambios HTML / bloqueo.
* Mitigación: backoff + fallback a otra estrategia simple (ej. Wikipedia/Docs oficiales si el query lo permite).

👉 Esto mantiene el proyecto 100% gratuito y reproducible localmente.

---

## 2) Persistencia HITL / reanudación: solo RAM (dict) ✅

**Decisión:** Para Sesión 4, **RAM-only** es suficiente.

**Implementación esperada:**

* Guardar estado por `session_id` en un `dict` global en el server (FastAPI).
* Flujo:

  * `/chat` corre el grafo.
  * Si `NEEDS_HITL`, devuelve `hitl_token` + `session_id` + resumen.
  * `/approve` reinyecta el estado guardado (por `hitl_token`) y continúa.

**Nota honesta:** si reinicias el server, se pierde. Está bien para el ejercicio.

---

## 3) “Claims respaldadas”: criterio simple, auditable, no “semántico mágico” ✅

**Decisión:** Regla práctica y verificable, sin embeddings/RAG.

**Criterio:**

* El `draft_answer` debe salir en **puntos numerados** (“Key Points”).
* Cada punto clave debe incluir al menos **1 cita (URL)** y un **snippet** usado.
* El guard valida:

  1. que el punto tenga URL(s),
  2. que exista al menos un snippet asociado a esa URL,
  3. que haya **overlap léxico mínimo** entre punto y snippet (heurística: palabras clave).

Si falla: `reflector` obliga a iterar o pide HITL si no hay evidencia suficiente.

Esto es:

* simple,
* repetible,
* y fácil de auditar en trazas.

---

## 4) Modelos por rol: validar al inicio + fallback controlado ✅

**Decisión:** Validar al boot.

**Regla:**

* Si un modelo asignado no existe en Ollama:

  * usar fallback predefinido (ej. `qwen2.5:7b` o `llama3.1:8b`, el que esté instalado),
  * y registrar warning en trazas + en `execution_summary`.
* Si no hay ningún modelo disponible: error claro con instrucciones (“instala X con ollama pull …”).

Nada de “inventar”.

---

## 5) Observabilidad LangSmith + Langfuse: adapter manual unificado ✅

**Decisión:** Adapter propio manual (no depender de callbacks de LangChain).

**Regla:**

* Siempre generar `run_id` UUID interno.
* Si LangSmith está configurado (env vars), además reportar `langsmith_run_id`.
* Si Langfuse está configurado, además reportar `langfuse_trace_id`.
* El adapter expone: `start_run`, `start_span`, `log_event`, `end_span`, `end_run`.

Esto da trazabilidad completa aunque uses 0% LangChain.

---

## 6) UI: HTML estática de una página ✅

**Decisión:** una sola página:

* `index.html` + JS fetch a:

  * `POST /chat`
  * `POST /approve`

Sin tooling, sin build.

---

## 7) Smoke test: señal verificable ✅

**Decisión:** Bandera estructurada.

**Regla:**

* El estado incluye `guard_executed: true/false`.
* `execution_summary.steps[]` debe contener un step con nombre fijo: `"anti_hallucination_guard"`.

El test aserta eso, no “logs”.

---

## 8) trace_id / run_id ✅

**Decisión:** siempre `run_id` interno UUID.

* `run_id`: siempre presente (interno)
* `trace_id`: alias del mismo o un id de “trace” interno
* `langsmith_run_id` y `langfuse_trace_id`: opcionales, solo si están activos

---

9. **Dependencias scraping:**
   No, en`requirements.txt` ya está `requests`, `beautifulsoup4` y **`lxml` opcional** (recomendado).
   También está incluida `urllib3` si lo necesitas, pero con requests basta.

10. **Smoke test determinista (sin red):**
   Sí. El smoke test **DEBE** usar stubs/mocks de `web_search` y `web_fetch` para ser determinista, evitar flakiness y no depender de red.
   Define fixtures con resultados “con evidencia” y “sin evidencia” para validar ambos caminos (SUCCESS y NEEDS_HITL).

11. **Formato de salida del LLM para `draft_answer`:**
   Sí, acepto **JSON estricto** (Pydantic) para imponer el formato.
   Estructura mínima sugerida:

* `question`
* `key_points: [{id, claim, citations:[{url, snippet_id}], confidence}]`
* `final_answer`
* `limitations`
* `followups`

El guard valida por `key_points` y sus citations.

12. **IDs (`run_id` vs `trace_id`):**

* `run_id`: UUID interno **siempre**.
* `trace_id`: **igual a `run_id`** (para simplicidad) en Session4.
* `langsmith_run_id` / `langfuse_trace_id`: opcionales si providers activos.

Con esto, puedes arrancar implementación cuando te dé la orden. Por ahora mantén todo preparado (plan + archivos a crear + cambios de requirements), y cuando te diga “GO” procedes a escribir en `Session4/`.

---

# Resumen de confirmación para tu VS Code

✅ 1) `web_search`: **scraping local** (DuckDuckGo HTML + BeautifulSoup)
✅ 2) HITL persistencia: **solo RAM** (dict por `session_id`)

Con esto, puede implementar “sin sorpresas” y sin meter dependencias pagadas.

Además una regla simple para “modo gratis robusto”:

* limitar a 3–5 resultados,
* 1–2 fetch por resultado,
* 1 consulta cada ~2s con backoff,
  para reducir bloqueos.

Si detectas un bloqueo por scraping (CAPTCHA/rate limit), registra el evento y fuerza fallback a NEEDS_HITL en lugar de inventar.