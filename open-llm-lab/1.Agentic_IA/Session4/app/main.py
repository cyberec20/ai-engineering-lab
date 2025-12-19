from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import os
from langgraph.checkpoint.memory import InMemorySaver

from app.api.routes import build_router
from app.core.config import load_config
from app.orchestrator.graphs.research_operator import GraphDeps, build_research_operator_graph
from app.orchestrator.llms.router import LLMRouter
from app.orchestrator.observability.factory import get_trace_manager
from app.orchestrator.tools.web_tools import WebTools
from app.orchestrator.utils.ollama import list_ollama_models


def create_app() -> FastAPI:
    config = load_config()
    if config.trace_provider == "none":
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGSMITH_TRACING"] = "false"
    elif config.trace_provider == "langfuse":
        # Avoid accidental LangSmith emission while testing Langfuse.
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGSMITH_TRACING"] = "false"
    available_models = list_ollama_models(config.ollama_base_url)  # best-effort
    llms = LLMRouter(config, available_models=available_models)
    web = WebTools(
        timeout_seconds=config.request_timeout_seconds,
        max_results=config.web_max_results,
        min_delay_seconds=config.web_min_delay_seconds,
        cache_ttl_seconds=config.web_cache_ttl_seconds,
        cache_max_entries=config.web_cache_max_entries,
    )
    trace_manager = get_trace_manager(config)

    checkpointer = InMemorySaver()
    builder = build_research_operator_graph(GraphDeps(config=config, llms=llms, web=web, tracer=trace_manager))
    graph = builder.compile(checkpointer=checkpointer)

    app = FastAPI(title="Session4 Research Operator", version="0.1.0")
    static_dir = Path(__file__).resolve().parent / "ui" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    ui_index = str(static_dir / "index.html")

    app.include_router(build_router(app_config=config, graph=graph, trace_manager=trace_manager, ui_index_path=ui_index))
    return app


app = create_app()
