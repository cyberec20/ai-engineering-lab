from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from app.core.config import AppConfig
from app.orchestrator.schemas.models import ChatResponse
from app.orchestrator.utils.ids import new_uuid
from app.orchestrator.utils.time import now_iso
from app.orchestrator.utils.lang import detect_language
from langchain_core.tracers.langchain import LangChainTracer
from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler
import os


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: Optional[str] = None
    language: Optional[str] = None


class ApproveRequest(BaseModel):
    session_id: str = Field(min_length=1)
    approved: bool
    notes: Optional[str] = None


def build_router(
    *,
    app_config: AppConfig,
    graph: Any,
    trace_manager: Any,
    ui_index_path: str,
):
    router = APIRouter()
    pending_interrupts: dict[str, dict[str, str]] = {}

    def _thread_config(thread_id: str, *, session_id: str | None = None, user_message: str | None = None) -> dict:
        cfg: dict = {"configurable": {"thread_id": thread_id}}
        # Native tracing uses callbacks + env vars (LangSmith/Langfuse).
        if app_config.trace_provider == "langsmith":
            cfg["callbacks"] = [LangChainTracer(project_name=os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT"))]
            cfg["metadata"] = {
                "session_id": session_id,
                "user_message": user_message,
                "trace_provider": "langsmith_native",
            }
            cfg["tags"] = ["session4", "research_operator", "native"]
        elif app_config.trace_provider == "langfuse":
            cfg["callbacks"] = [LangfuseCallbackHandler(update_trace=True)]
            cfg["metadata"] = {
                "session_id": session_id,
                "user_message": user_message,
                "trace_provider": "langfuse_native",
            }
            cfg["tags"] = ["session4", "research_operator", "native"]
        return cfg

    @router.get("/")
    def index():
        return FileResponse(ui_index_path)

    @router.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest):
        session_id = req.session_id or new_uuid()
        run_id = new_uuid()
        trace_id = run_id

        provider_ids: dict = {}
        if app_config.trace_provider not in {"langsmith", "langfuse"}:
            provider_ids = trace_manager.start_run(
                name="research_operator",
                run_id=run_id,
                trace_id=trace_id,
                inputs={"user_message": req.message, "session_id": session_id},
                metadata={
                    "session_id": session_id,
                    "started_at": now_iso(),
                    "trace_provider": app_config.trace_provider,
                },
            )

        detected_lang = detect_language(req.message)
        requested_lang = (req.language or "").lower().strip()
        # "Language of input" wins. If the message looks non-English, trust detection even if UI sends a stale value.
        if requested_lang in {"", "auto"}:
            input_language = detected_lang
        else:
            input_language = detected_lang if detected_lang != "en" else requested_lang

        state = {
            "user_message": req.message,
            "input_language": input_language,
            "plan": [],
            "queries": [],
            "web_results": [],
            "snippets": {},
            "sources": [],
            "draft_answer": None,
            "final_answer": "",
            "iteration_count": 0,
            "hitl_required": False,
            "hitl_notes": None,
            "guard_executed": False,
            "run_id": run_id,
            "trace_id": trace_id,
            "timestamps": {"started_at": now_iso()},
            "execution_summary": [],
            **provider_ids,
        }

        # Important: isolate graph state per message/run to avoid cross-turn contamination.
        config = _thread_config(run_id, session_id=session_id, user_message=req.message)
        interrupted: Optional[str] = None
        try:
            for chunk in graph.stream(state, config):
                if "__interrupt__" in chunk:
                    interrupts = chunk["__interrupt__"]
                    interrupted = interrupts[0].id
                    pending_interrupts[session_id] = {"interrupt_id": interrupted, "thread_id": run_id}
                    break
        except GraphInterrupt:
            pass
        except Exception as e:
            if app_config.trace_provider not in {"langsmith", "langfuse"}:
                trace_manager.end_run(run_id=run_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

        snapshot = graph.get_state(config)
        current = snapshot.values

        if interrupted:
            return ChatResponse(
                session_id=session_id,
                run_id=current.get("run_id") or run_id,
                trace_id=current.get("trace_id") or trace_id,
                answer=None,
                execution_summary=current.get("execution_summary") or [],
                sources=current.get("sources") or [],
                status="NEEDS_HITL",
                hitl_required=True,
                hitl_token=interrupted,
                hitl_notes=current.get("hitl_notes"),
                langsmith_run_id=current.get("langsmith_run_id"),
                langfuse_trace_id=current.get("langfuse_trace_id"),
            )

        if app_config.trace_provider not in {"langsmith", "langfuse"}:
            trace_manager.end_run(
                run_id=run_id,
                outputs={"status": current.get("status"), "sources": current.get("sources")},
            )
        status = current.get("status") or "FAILED"
        if status not in {"SUCCESS", "NEEDS_HITL", "FAILED"}:
            status = "FAILED"

        return ChatResponse(
            session_id=session_id,
            run_id=current.get("run_id") or run_id,
            trace_id=current.get("trace_id") or trace_id,
            answer=current.get("final_answer"),
            execution_summary=current.get("execution_summary") or [],
            sources=current.get("sources") or [],
            status=status,
            hitl_required=bool(current.get("hitl_required")),
            hitl_token=None,
            hitl_notes=current.get("hitl_notes"),
            langsmith_run_id=current.get("langsmith_run_id"),
            langfuse_trace_id=current.get("langfuse_trace_id"),
        )

    @router.post("/approve", response_model=ChatResponse)
    def approve(req: ApproveRequest):
        session_id = req.session_id
        pending = pending_interrupts.get(session_id)
        if not pending:
            raise HTTPException(status_code=404, detail="No pending HITL interrupt for this session_id")
        interrupt_id = pending["interrupt_id"]
        thread_id = pending["thread_id"]

        config = _thread_config(thread_id, session_id=session_id)
        snapshot = graph.get_state(config)
        current = snapshot.values
        run_id = current.get("run_id")
        trace_id = current.get("trace_id")
        if not run_id:
            raise HTTPException(status_code=409, detail="Missing run_id for this session; restart session")

        resume_value = {"approved": req.approved, "notes": req.notes}
        cmd = Command(resume={interrupt_id: resume_value})

        new_interrupt: Optional[str] = None
        try:
            for chunk in graph.stream(cmd, config):
                if "__interrupt__" in chunk:
                    interrupts = chunk["__interrupt__"]
                    new_interrupt = interrupts[0].id
                    pending_interrupts[session_id] = {"interrupt_id": new_interrupt, "thread_id": thread_id}
                    break
        except GraphInterrupt:
            pass
        except Exception as e:
            if run_id:
                if app_config.trace_provider not in {"langsmith", "langfuse"}:
                    trace_manager.end_run(run_id=run_id, error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

        snapshot2 = graph.get_state(config)
        final_state = snapshot2.values

        if new_interrupt:
            return ChatResponse(
                session_id=session_id,
                run_id=run_id,
                trace_id=trace_id or run_id,
                answer=None,
                execution_summary=final_state.get("execution_summary") or [],
                sources=final_state.get("sources") or [],
                status="NEEDS_HITL",
                hitl_required=True,
                hitl_token=new_interrupt,
                hitl_notes=final_state.get("hitl_notes"),
                langsmith_run_id=final_state.get("langsmith_run_id"),
                langfuse_trace_id=final_state.get("langfuse_trace_id"),
            )

        if app_config.trace_provider not in {"langsmith", "langfuse"}:
            trace_manager.end_run(
                run_id=run_id,
                outputs={"status": final_state.get("status"), "sources": final_state.get("sources")},
            )
        pending_interrupts.pop(session_id, None)

        status = final_state.get("status") or "FAILED"
        if status not in {"SUCCESS", "NEEDS_HITL", "FAILED"}:
            status = "FAILED"

        return ChatResponse(
            session_id=session_id,
            run_id=run_id,
            trace_id=trace_id or run_id,
            answer=final_state.get("final_answer"),
            execution_summary=final_state.get("execution_summary") or [],
            sources=final_state.get("sources") or [],
            status=status,
            hitl_required=bool(final_state.get("hitl_required")),
            hitl_token=None,
            hitl_notes=final_state.get("hitl_notes"),
            langsmith_run_id=final_state.get("langsmith_run_id"),
            langfuse_trace_id=final_state.get("langfuse_trace_id"),
        )

    return router
