from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.core.config import AppConfig
from app.orchestrator.research_operator import ApproveCommand, ResearchOperator


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    session_id: str | None = None


class ApproveRequest(BaseModel):
    session_id: str = Field(..., min_length=1)
    approved: bool
    notes: str | None = None


def build_router(*, config: AppConfig, operator: ResearchOperator, ui_index_path: str) -> APIRouter:  # noqa: ARG001
    router = APIRouter()
    index_file = Path(ui_index_path)

    @router.get("/", include_in_schema=False)
    def ui_index() -> FileResponse:
        return FileResponse(str(index_file))

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.post("/chat")
    def chat(req: ChatRequest) -> JSONResponse:
        session_id = req.session_id or str(uuid.uuid4())
        started = time.time()
        result = operator.chat(user_message=req.message, session_id=session_id)
        elapsed = time.time() - started
        payload: dict[str, Any] = dict(result)
        payload["session_id"] = session_id
        payload.setdefault("execution_summary", [])
        payload["execution_summary"].append(
            {"name": "api", "status": "OK", "details": {"latency_seconds": round(elapsed, 3)}}
        )
        return JSONResponse(payload)

    @router.post("/approve")
    def approve(req: ApproveRequest) -> JSONResponse:
        cmd = ApproveCommand(session_id=req.session_id, approved=req.approved, notes=req.notes)
        result = operator.approve(cmd)
        return JSONResponse(dict(result))

    return router

