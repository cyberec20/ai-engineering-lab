from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Configure logging for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
from app.api.routes import build_router
from app.core.config import load_config
from app.orchestrator.engine import SessionStore
from app.orchestrator.research_operator import ResearchOperator


def create_app() -> FastAPI:
    config = load_config()

    # Avoid duplicate LangSmith roots produced by env-based auto-tracing (e.g., LLM calls creating their own roots).
    if config.trace_provider in {"langsmith", "langfuse"}:
        import os

        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        os.environ["LANGSMITH_TRACING"] = "false"

    store = SessionStore(ttl_seconds=config.session_ttl_seconds, max_sessions=config.session_max_entries)
    operator = ResearchOperator(config=config, store=store)

    app = FastAPI(title="Session5.1 Research Operator", version="0.1.0")

    @app.get("/__whoami")
    async def __whoami() -> dict[str, str | int]:
        # Defined at app-level (not only router) to guarantee availability for debugging import/path issues.
        return {"app": "Session5_1", "port": config.port}

    @app.head("/__whoami")
    async def __whoami_head() -> None:
        return None

    @app.get("/__routes")
    async def __routes() -> dict[str, list[str]]:
        return {"routes": [getattr(r, "path", "") for r in app.router.routes]}

    @app.middleware("http")
    async def _no_cache_and_tag(request, call_next):  # type: ignore[no-untyped-def]
        response = await call_next(request)
        response.headers.setdefault("X-App-Name", "Session5_1")
        # Avoid stale pages/assets when reusing the same localhost:8100 across sessions.
        if request.url.path in {"/", "/__whoami"} or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    static_dir = Path(__file__).resolve().parent / "ui" / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    ui_index_path = str(static_dir / "index.html")

    app.include_router(build_router(config=config, operator=operator, ui_index_path=ui_index_path))
    return app


app = create_app()
