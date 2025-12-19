from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

from app.core.config import AppConfig
from app.orchestrator.research_operator import ApproveCommand, ResearchOperator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str | None = None


class ApproveRequest(BaseModel):
    session_id: str
    approved: bool
    notes: str | None = None


def build_router(*, config: AppConfig, operator: ResearchOperator, ui_index_path: str) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    def index() -> FileResponse:
        # Avoid browser caching during rapid iteration across sessions sharing the same port.
        return FileResponse(
            ui_index_path,
            headers={"Cache-Control": "no-store, max-age=0"},
        )

    @router.head("/")
    def index_head() -> Response:
        return Response(status_code=200, headers={"Cache-Control": "no-store, max-age=0"})

    @router.get("/__whoami")
    def whoami() -> JSONResponse:
        return JSONResponse({"app": "Session5_1", "port": config.port}, headers={"Cache-Control": "no-store, max-age=0"})

    @router.head("/__whoami")
    def whoami_head() -> Response:
        return Response(status_code=200, headers={"Cache-Control": "no-store, max-age=0"})

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/chat")
    def chat(req: ChatRequest) -> dict[str, Any]:
        session_id = req.session_id or operator.ensure_session()
        result = operator.chat(user_message=req.message, session_id=session_id)
        return result.model_dump()

    @router.post("/approve")
    def approve(req: ApproveRequest) -> dict[str, Any]:
        result = operator.approve(ApproveCommand(session_id=req.session_id, approved=req.approved, notes=req.notes))
        return result.model_dump()

    return router
