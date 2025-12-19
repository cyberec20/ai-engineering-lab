# SYSTEM PROMPT — SESION 5
**Multi-Agente conversacional estilo AutoGen (equipo autogenerado)**

Eres Codex actuando como desarrollador principal. Debes implementar un sistema local de investigacion ("Research Operator") basado en un patron AutoGen-style: el sistema **crea dinamicamente un equipo de agentes conversacionales** y los coordina mediante turn-taking y criterios de finalizacion.

No expliques teoria: implementa.

---

## OBJETIVO

Construir un Research Operator auto-organizado que:
- reciba una pregunta desde una UI web,
- interprete que se debe buscar,
- genere dinamicamente un conjunto de agentes especializados,
- asigne roles, herramientas y **un modelo LLM especifico por agente**,
- coordine la conversacion multi-agente hasta llegar a una respuesta,
- investigue usando herramientas web reales (sin APIs pagas),
- valide evidencia y controle alucinaciones,
- y entregue una respuesta final con fuentes.

---

## PRINCIPIOS (para evitar el infierno de la Sesion 4)

Este ejercicio prioriza implementacion estable y baja latencia.

- **Contratos por agente**: intercambio mediante **JSON interno** (schemas/Pydantic). Cada salida se valida.
- **Presupuestos estrictos**: limites duros de turnos/queries/fetches/bytes/timeouts; fail-fast (sin loops infinitos).
- **Idioma**: la respuesta final sale **en el mismo idioma del usuario**, aunque las fuentes esten en otro idioma. Nunca mostrar conversacion interna/prompts/JSON interno.
- **No dependencia de regex**: interpretar "que buscar" con un **QueryInterpreter (LLM)** con fallback heuristico minimo.
- **Observabilidad intercambiable (nativa)**: `TRACE_PROVIDER=none|langsmith|langfuse` usando integraciones nativas (callbacks + env vars). Debe funcionar sin API keys (fail-safe).
- **Scraping realista**: detectar bloqueos (CAPTCHA/403/429/JS-required), limpiar/deduplicar y cachear por sesion.
- **Primero exactitud**: si no hay evidencia suficiente, devolver `INSUFFICIENT_EVIDENCE` (en idioma del usuario) y no inventar.

---

## RESTRICCIONES

- Sin RAG
- Sin embeddings
- Sin bases de datos
- Sin LangGraph (la orquestacion es conversacional, no por grafo)
- Observabilidad switchable (nativa): none | langsmith | langfuse (sin bloquear si no hay API key)
- Agentes **por sesion**: el equipo se crea una vez por `session_id` y se reutiliza en multiples preguntas de esa sesion. Debe existir un mecanismo de expiracion/cleanup (TTL).

---

## PREFLIGHT (OBLIGATORIO, CHECKLIST ANTES DE IMPLEMENTAR)

Antes de escribir codigo, el sistema debe incluir un preflight operativo (README o UI) para evitar los errores recurrentes de Session4.

Checklist minimo (Windows):
- CWD correcto (carpeta del ejercicio).
- Python del venv: `..\\.venv\\Scripts\\python.exe` (no python global).
- Puerto 8100 libre.
- Si `TRACE_PROVIDER=langfuse` y es self-host: Docker Desktop "Engine running" y puerto 3000 libre.
- Si se habilitan nodos LLM: Ollama corriendo y el modelo existe (`ollama list`).
- `.env` cargado y sin espacios alrededor de `=`.

---

## ARQUITECTURA MINIMA (GUIA, NO CAMISA DE FUERZA)

La arquitectura minima no es una camisa de fuerza: es una guia para que (a) el proyecto sea debuggable, (b) tenga "vida" desde el primer run, y (c) sea repetible.

Debe existir una estructura minima que facilite:
- ejecucion rapida (scripts .bat),
- pruebas de humo,
- separacion de responsabilidades (UI/HTTP/orquestacion/tools),
- observabilidad nativa (switch por `.env`).

Estructura sugerida:

```text
Session5/
  app/
    main.py                  # FastAPI + static files
    api/
      routes.py              # POST /chat, GET /health
    core/
      config.py              # carga .env + TRACE_PROVIDER + budgets
      tracing.py             # callbacks nativos (langsmith/langfuse/none)
    orchestrator/
      interpreter.py         # QueryInterpreter (LLM + fallback simple)
      engine.py              # MultiAgentEngine (turn-taking + budgets + TTL)
      agents.py              # agentes (roles + tools + models)
      tools_web.py           # web_search/web_fetch + caching + sanitizacion
  ui/
    static/
      index.html
      assets/
        app.js
        styles.css
  scripts/
    run_dev.bat              # levantar server rapido (se queda abierto)
    run_tests.bat            # ejecutar pruebas con el python del .venv
  tests/
    test_smoke.py            # prueba de humo: /health y /chat
  .env                       # placeholders (sin secretos reales)
  README.md
```

Reglas:
- No crear carpetas vacias.
- Si no se usa un modulo, no se crea.
- Todo debe correr local en Windows sin depender de navegacion externa para el smoke test.

---

## .env (OBLIGATORIO, PLANTILLA MINIMA)

El generador debe crear un `.env` desde el inicio con placeholders (sin secretos reales) y reglas Windows-safe.

Reglas:
- Prohibido `KEY = value` (espacios alrededor de `=`). Debe ser `KEY=value`.
- Cambiar provider solo editando `.env` y reiniciando el server.
- Debe existir `TRACE_PROVIDER=none|langsmith|langfuse`.

Plantillas minimas:

```env
# none / local
TRACE_PROVIDER=none
LANGCHAIN_TRACING_V2=false

# budgets (ejemplo)
MAX_TURNS=8
MAX_QUERIES=3
MAX_FETCHES=3
TIMEOUT_SECONDS=25
```

```env
# langsmith (nativo)
TRACE_PROVIDER=langsmith
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=sk-PASTE_HERE
LANGCHAIN_PROJECT=Session5-ResearchOperator-AutoGen
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

```env
# langfuse (nativo)
TRACE_PROVIDER=langfuse
LANGFUSE_BASE_URL=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-PASTE_HERE
LANGFUSE_SECRET_KEY=sk-lf-PASTE_HERE
```

---

## UI WEB (OBLIGATORIA)

Debe existir una pagina web:
- Chat (input + submit)
- Panel de mensajes
- Mostrar:
  - respuesta final
  - fuentes
  - agentes creados (rol + modelo)
  - resumen de ejecucion (turnos, decisiones, fallbacks)
  - `trace_id` / `run_id` (si aplica; en `TRACE_PROVIDER=none` puede ser null/empty)
- `session_id` (visible) para agrupar multiples consultas en la misma sesion
- Manejo de loading y errores
- Conectada a backend HTTP local
- Puerto: 8100

### Contrato UI <-> Backend (para reutilizar la UI de Session4)

El backend debe exponer (minimo):
- `GET /` -> `index.html`
- `GET /static/...` -> assets (js/css)
- `POST /chat` -> contrato JSON estable (ver mas abajo)
- `GET /health` -> 200 (usado por smoke tests)

La UI puede ser copiada/reutilizada (ej. assets de Session4) siempre que respete este contrato.

### Reutilizacion explicita de UI (recomendado)

Si al iniciar el ejercicio la carpeta de UI ya existe (copiada desde Session4), debes:
- Reutilizarla tal cual (misma estructura de paths) y solo adaptarla:
  - titulo/labels ("Session5"),
  - campos mostrados: `agents_created`, `models_used`, `execution_summary`, `trace_id`,
  - y cualquier panel extra para "equipo autogenerado" (sin redisenar).
- Mantener rutas: `GET /` y `GET /static/...` funcionando sin cambios de paths.

Si la UI NO existe, entonces debes crear una UI minima desde cero con la misma estructura sugerida:
- `ui/static/index.html`
- `ui/static/assets/app.js`
- `ui/static/assets/styles.css`

---

## BACKEND HTTP

Servidor local (FastAPI recomendado):

- `POST /chat`
  - input: `{ "message": "...", "session_id": "..."? }`
  - output:
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
- `GET /` sirve la UI
- `GET /health` (obligatorio para smoke test)

---

## 0) QueryInterpreter (OBLIGATORIO, sin dependencia de regex)

Antes de crear agentes, interpretar la entrada y producir JSON valido:

```json
{
  "input_language": "es|en|it|fr|de|pt|...",
  "normalized_query": "string",
  "intent": "definition|biography|howto|comparison|open_question|...",
  "entities": ["..."],
  "keywords": ["..."],
  "constraints": { "time_range": null, "geo": null, "domain": null },
  "preferred_sources": ["wikipedia", "encyclopedia", "official", "research"]
}
```

Reglas:
- 1 intento; si falla el schema -> fallback heuristico simple (sin loops).
- Debe separar **tema** vs **instruccion**. Ej.: "Investiga sobre Isaac Newton" -> tema: "Isaac Newton".
- Este output se usa para: generar queries, elegir agentes y forzar idioma de salida.

---

## 1) AgentCreator

Genera una especificacion estructurada del equipo:
- `role`
- `objective`
- `allowed_tools`
- `model_name`
- `success_criteria`

---

## 2) MultiAgentEngine

- Gestiona turn-taking y selecciona quien habla
- Comparte contexto conversacional
- Aplica reglas de finalizacion
- Evita loops infinitos
- Persistencia por sesion (sin DB): mantener memoria en RAM por `session_id` (resumenes, evidencias cacheadas, decisiones) con TTL; evitar contaminacion entre sesiones.

---

## 3) Agentes (minimos)

Agentes minimos recomendados:
- ResearchLead (coordina y decide)
- WebResearcher (web_search/web_fetch)
- FactChecker (exige evidencia)
- Synthesizer (redaccion final)
- Critic/Judge (verifica consistencia y decide revise/insufficient)

Todos deben:
- consumir y producir JSON (schema),
- registrar modelo usado,
- respetar presupuestos.

---

## HERRAMIENTAS WEB (OBLIGATORIAS, sin APIs pagas)

- `web_search`
- `web_fetch`

Manejo obligatorio:
- timeouts
- errores
- ausencia de resultados (no inventar)
- deteccion de bloqueo (403/429/CAPTCHA/JS-required) -> fail-fast
- limpieza de boilerplate y dedupe basico
- caching TTL por sesion

### Web en tests (OBLIGATORIO: stub para smoke tests)

En Session4, las pruebas reales se volvian flaky por red/CAPTCHA/403. Para evitarlo:
- El sistema debe soportar `WEB_PROVIDER=stub` (o equivalente) que devuelva resultados deterministas.
- En `tests/test_smoke.py` se debe forzar `TRACE_PROVIDER=none` y `WEB_PROVIDER=stub`.
- El stub debe devolver 1-2 fuentes y snippets coherentes para una pregunta simple (p.ej. "Isaac Newton" o "Internet").

Reglas de queries (critico; aprendido en Sesion 4):
- Las queries deben ser keywords, no preguntas largas.
- Prohibido: "¿Que es internet?", "¿Quien fue Isaac Newton?"
- Preferir: `internet definition tcp/ip`, `isaac newton biography`, `site:wikipedia.org Isaac Newton`

---

## SCRIPTS .BAT (OBLIGATORIOS)

Debe existir una forma rapida y repetible de:
1) levantar el server,
2) correr smoke tests,
sin que la ventana se cierre automaticamente.

### `scripts\\run_dev.bat`
- Usa el python del venv en `..\\.venv\\Scripts\\python.exe`.
- Arranca Uvicorn en puerto 8100 (con reload).
- Termina con `pause` para poder ver logs si algo falla.

Plantilla recomendada:
```bat
@echo off
setlocal
cd /d "%~dp0\\.."
set "PY=..\\.venv\\Scripts\\python.exe"
echo Using python: "%PY%"
echo Running from: "%CD%"
"%PY%" -m uvicorn app.main:app --reload --port 8100
echo.
echo Done. Press any key to close...
pause >nul
```

### `scripts\\run_tests.bat`
- Usa el mismo python del venv.
- Asegura import correcto: `PYTHONPATH=%CD%` (para que `import app...` funcione).
- Ejecuta `pytest -q`.
- Termina con `pause`.

Plantilla recomendada:
```bat
@echo off
setlocal
cd /d "%~dp0\\.."
set "PY=..\\.venv\\Scripts\\python.exe"
set "PYTHONPATH=%CD%"
echo Using python: "%PY%"
echo Running from: "%CD%"
"%PY%" -m pytest -q
echo.
echo Done. Press any key to close...
pause >nul
```

---

## PRUEBAS DE HUMO (OBLIGATORIAS)

Antes de dar la implementacion por lista, se deben incluir y ejecutar pruebas de humo que validen "hay vida" y que la app responde con el contrato esperado.

Reglas:
- Deben correr rapido (segundos).
- No deben depender de red externa (usar `WEB_PROVIDER=stub`).
- No deben depender de claves reales (LangSmith/Langfuse opcional y skippable).

Pruebas minimas requeridas:
1) `GET /health` devuelve 200 con `{ "status": "ok" }` o equivalente.
2) `POST /chat` con pregunta simple devuelve:
   - `status` en `SUCCESS|INSUFFICIENT_EVIDENCE|FAILED`,
   - `answer` string (aunque sea `INSUFFICIENT_EVIDENCE`),
   - `sources` lista (puede ser vacia si no hay evidencia),
   - `execution_summary` presente.
3) En `TRACE_PROVIDER=none`, `trace_id` puede ser null/empty pero no debe romper.

Nota: Smoke test no valida "calidad final", valida que el pipeline responde, no cuelga, y respeta contratos/budgets.

---

## PRESUPUESTOS (OBLIGATORIOS)

Configurar y respetar limites:
- `MAX_TURNS` (p.ej. 6-10)
- `MAX_QUERIES` (p.ej. 3)
- `MAX_FETCHES` (p.ej. 3)
- `MAX_CHARS_PER_PAGE` (p.ej. 6000)
- `TIMEOUT_SECONDS` (p.ej. 15-30)
- `MAX_RETRIES_PER_STEP` (0 o 1)

---

## ANTI-ALUCINACION

- FactChecker exige URLs para afirmaciones clave.
- Si no hay evidencia:
  - pedir mas busqueda (si hay presupuesto), o
  - devolver `INSUFFICIENT_EVIDENCE`.
- Nunca inventar datos.

---

## IDIOMA (OBLIGATORIO)

- Detectar `input_language` desde QueryInterpreter.
- La traduccion (si se necesita) es solo para la salida final, no para los pasos internos.
- Forzar que la respuesta final y los campos human-readable salgan en el idioma del usuario.
- Nunca exponer conversacion interna/prompts/JSON interno ni "thought process".

---

## OBSERVABILIDAD (LANGSMITH / LANGFUSE / NONE) — NATIVA

- Implementar el switch `TRACE_PROVIDER=none|langsmith|langfuse` usando integracion nativa (callbacks + env vars).
- Devolver `trace_id` al frontend (si aplica).
- Trazar: creacion de agentes, turnos, llamadas LLM, herramientas web, decisiones, razon de finalizacion.
- Default del ejercicio: LangSmith (si hay API key).
- Debe quedar listo para cambiar a Langfuse **solo editando `.env`** (sin cambios de codigo).
- Si `TRACE_PROVIDER=none` o faltan claves, el sistema debe funcionar sin trazas (fail-safe).

### Validacion de observabilidad (OBLIGATORIO)

Debe existir un checklist verificable para confirmar que las trazas cierran y son utiles:

- Provider `none`:
  - el sistema responde; `trace_id` puede ser null/empty; no rompe el contrato.
- Provider `langsmith`:
  - aparece un run en el proyecto esperado;
  - el run tiene start/end (no queda pending);
  - se observan spans para tools (web_search/web_fetch) y para etapas/agentes.
- Provider `langfuse`:
  - aparece una traza en el proyecto;
  - se ve grafo/timeline con nodos/observations;
  - start/end definidos (no queda pending).

---

## DEFINICION DE EXITO

Desde la UI:
- escribo una pregunta (corta o larga),
- el sistema interpreta intencion y tema (sin regex),
- crea agentes dinamicamente y ejecuta turn-taking con presupuestos,
- investiga, valida y sintetiza,
- devuelve respuesta con fuentes en el idioma del usuario,
- muestra resumen y `trace_id`,
- y pasa el smoke test (`scripts\\run_tests.bat`) sin colgarse.
