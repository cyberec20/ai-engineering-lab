# Session4 - Research Operator (No RAG, Web, UI, Observability)

## Run (dev)
- Copy `.env.example` to `.env` and fill placeholders.
- `scripts\run_dev.bat` (serves UI at `http://127.0.0.1:8100/`).

## Test
- `scripts\run_tests.bat`

## Tracing (LangSmith / Langfuse)
- **LangSmith (native)**: in `.env` set `TRACE_PROVIDER=langsmith`, set `LANGCHAIN_API_KEY=...`, and set `LANGCHAIN_TRACING_V2=true`, then restart the server. This uses native LangChain/LangGraph tracing via callbacks (recommended for stability).
- **Langfuse (native)**: in `.env` set `TRACE_PROVIDER=langfuse`, set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, then restart the server. This uses Langfuse's native LangChain callback handler.

## Performance knobs
- `GRAPH_MODE=fast` keeps the LangGraph flow but minimizes web/LLM calls to avoid multi-minute latency.
- Toggle LLM usage per node with `ENABLE_LLM_*` and translation retries with `TRANSLATION_RETRIES` (see `.env.example`).
- Web fetch limits are controlled by `WEB_*` settings in `.env.example`.

## UI and docs
- UI assets live in `app\ui\static\` (`index.html`, `assets\app.js`, `assets\styles.css`).
- Learning material: `Session4_ResearchOperator_Roadmap.html`, `Session4_Study_Notes.html`, `docs/03_langfuse_self_host_windows.md`, `docs/04_runtime_guardrails.md`.

## From exercise -> product (practical guidance)
This exercise is intentionally hard mode: web research without RAG, with local LLMs, and with strict structured outputs. It is great for learning LangGraph, and it becomes even more valuable once you enable tracing (LangSmith/Langfuse) to see latency and failures per node.

When turning this into a real product, plan the workflow like an integration pipeline (similar to tools like n8n):
- Define node contracts early: for each node/model, specify inputs, outputs, and schema (Pydantic). Keep them minimal and stable.
- Use structured state as the backbone: nodes should read/write the graph state via explicit keys (`queries`, `snippets`, `draft_answer`, `status`, etc.). This enables deterministic routing and better observability.
- Design parsing strategy: if a model struggles with strict JSON, use one of these patterns:
  - a dedicated formatter model for schema compliance,
  - single-attempt generation + deterministic fallback (avoid long repair loops),
  - best effort extraction + validation (fail fast when invalid).
- Plan fallbacks per node (not globally): define what happens when a node fails (no evidence, invalid schema, fetch blocked, timeout). Prefer localized fallback and keep the graph running.
- Choose evidence sources deliberately:
  - Scraping is fragile (HTML changes, boilerplate, CAPTCHAs). It needs more normalization, dedupe, and caching.
  - APIs (Wikipedia, news/search APIs, domain APIs) are more stable and reduce parsing complexity.
  - RAG (your own corpus + vector store) is the most stable for product-grade reliability and latency.
- Control latency explicitly: set timeouts, cap results/fetches, add caching, and avoid nice-to-have LLM calls that do not change the final answer.

## Docs
- docs/01_system_prompt.md
- docs/02_langsmith_tracing_fix.md
- docs/03_langfuse_self_host_windows.md
- docs/04_runtime_guardrails.md
## Optional (recommended)
- Install `langchain-ollama` to remove the `ChatOllama` deprecation warning: `pip install langchain-ollama`

