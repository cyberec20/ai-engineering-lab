from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import build_router
from app.core.config import load_config
from app.orchestrator.engine import SessionStore
from app.orchestrator.research_operator import ResearchOperator


def create_app() -> FastAPI:
    config = load_config()
    # Avoid duplicate LangSmith roots produced by env-based auto-tracing (e.g., ChatOllama creating its own root runs).
    # Session5 uses an explicit root run (RunTree) and spans for internal steps.
    if config.trace_provider in {"langsmith", "langfuse"}:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGSMITH_TRACING"] = "false"
    store = SessionStore(ttl_seconds=config.session_ttl_seconds, max_sessions=config.session_max_entries)
    operator = ResearchOperator(config=config, store=store)

    app = FastAPI(title="Session5 Research Operator", version="0.1.0")
    static_dir = Path(__file__).resolve().parent / "ui" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    ui_index_path = str(static_dir / "index.html")

    app.include_router(build_router(config=config, operator=operator, ui_index_path=ui_index_path))
    return app


app = create_app()
