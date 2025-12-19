from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.core.config import AppConfig
from app.core.tracing import traced_root_run
from app.orchestrator.crewai_tools import build_crewai_tools
from app.orchestrator.crew_factory import build_crew
from app.orchestrator.engine import SessionStore
from app.orchestrator.interpreter import QueryInterpreter
from app.orchestrator.models import (
    ApproveResult,
    ChatResult,
    DraftOutput,
    EvidenceItem,
    InterpreterOutput,
    PlanOutput,
    VerdictOutput,
    WebResearchOutput,
)
from app.orchestrator.tools_web import WebTools, polite_delay


@dataclass(frozen=True)
class ApproveCommand:
    session_id: str
    approved: bool
    notes: str | None = None


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _parse_task_output(task) -> Any:  # type: ignore[no-untyped-def]
    out = getattr(task, "output", None)
    if out is None:
        return None
    # CrewAI TaskOutput often has .raw or .json_dict
    raw = getattr(out, "raw", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    json_dict = getattr(out, "json_dict", None)
    if isinstance(json_dict, dict):
        return json_dict
    return raw


def _load_model_output(payload: Any, model_cls):  # type: ignore[no-untyped-def]
    if isinstance(payload, model_cls):
        return payload
    if isinstance(payload, dict):
        return model_cls.model_validate(payload)
    if isinstance(payload, str):
        # If the LLM returned JSON as text, parse it.
        # Handle markdown code blocks: ```json ... ``` or ``` ... ```
        text = payload.strip()
        logging.info(f"Parsing string payload for {model_cls.__name__}, starts with backticks: {text.startswith('```')}")
        if text.startswith("```"):
            # Extract content between code fences
            lines = text.split("\n")
            # Remove first line (```json or ```)
            lines = lines[1:]
            # Find closing ```
            end_idx = len(lines)
            for i, line in enumerate(lines):
                if line.strip() == "```":
                    end_idx = i
                    break
            text = "\n".join(lines[:end_idx]).strip()
            logging.info(f"Extracted JSON from code block, length: {len(text)}")
        
        # Parse JSON with strict=False to allow control characters
        data = json.loads(text, strict=False)
        
        # Handle case where WebResearcher returns a list instead of {"evidence": [...]}
        if isinstance(data, list) and model_cls.__name__ == "WebResearchOutput":
            data = {"evidence": data}
        
        return model_cls.model_validate(data)
    raise ValueError("Unsupported payload type")


class ResearchOperator:
    def __init__(self, *, config: AppConfig, store: SessionStore) -> None:
        self._config = config
        self._store = store
        self._interpreter = QueryInterpreter(config=config)
        self._web = WebTools(config=config)

    def ensure_session(self) -> str:
        return self._store.new_session_id()

    def _ensure_crew(self, session_id: str, tracer) -> dict[str, Any]:  # type: ignore[no-untyped-def]
        cached = self._store.get(session_id, "crew_bundle")
        if cached:
            return cached
        web_tools = build_crewai_tools(web=self._web, tracer=tracer)
        bundle, _tasks_yaml, _tools_yaml = build_crew(config=self._config, web_tools=web_tools)
        self._store.set(session_id, "crew_bundle", bundle)
        self._store.set(session_id, "agents_created", bundle.agents_created)
        self._store.set(session_id, "models_used", sorted({a["model"] for a in bundle.agents_created}))
        return bundle

    def chat(self, *, user_message: str, session_id: str) -> ChatResult:
        with traced_root_run(
            config=self._config,
            name="research_operator",
            inputs={"session_id": session_id, "user_message": user_message},
        ) as (trace, tracer):
            execution: list[dict[str, Any]] = []
            started = datetime.now(timezone.utc).isoformat()
            try:
                with tracer.span("query_interpreter", {"user_message": user_message}) as span:
                    interp = self._interpreter.interpret(user_message)
                    span.end(
                        {
                            "input_language": interp.input_language,
                            "intent": interp.intent,
                            "normalized_query": interp.normalized_query,
                            "entities": interp.entities[:3],
                            "keywords": interp.keywords[:8],
                        }
                    )
                execution.append(
                    {
                        "name": "query_interpreter",
                        "status": "OK",
                        "started_at": started,
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                        "details": interp.model_dump(),
                    }
                )

                bundle = self._ensure_crew(session_id, tracer)
                agents_created = self._store.get(session_id, "agents_created", []) or []
                models_used = self._store.get(session_id, "models_used", []) or []

                # Provide interpreter JSON as context for the crew.
                kickoff_inputs = {"interpreter": interp.model_dump(), "user_message": user_message}

                with tracer.span("crew_kickoff", {"tasks": len(bundle.tasks)}) as span:
                    result = bundle.crew.kickoff(inputs=kickoff_inputs)
                    span.end({"ok": True, "result_type": type(result).__name__})

                # Extract per-task outputs (must be non-empty for useful traces).
                plan_out: PlanOutput | None = None
                web_out: WebResearchOutput | None = None
                fact_out: VerdictOutput | None = None
                draft_out: DraftOutput | None = None
                critic_out: VerdictOutput | None = None

                for t in bundle.tasks:
                    payload = _parse_task_output(t)
                    name = getattr(t, "name", "task")
                    detail_preview: dict[str, Any] = {"ok": payload is not None}
                    if isinstance(payload, dict):
                        detail_preview["keys"] = list(payload.keys())[:10]
                    elif isinstance(payload, str):
                        detail_preview["chars"] = len(payload)
                    execution.append({"name": name, "status": "OK" if payload else "WARN", "details": detail_preview})

                    try:
                        if name == "planning" and payload:
                            plan_out = _load_model_output(payload, PlanOutput)
                        elif name == "web_research" and payload:
                            web_out = _load_model_output(payload, WebResearchOutput)
                        elif name == "fact_check" and payload:
                            fact_out = _load_model_output(payload, VerdictOutput)
                        elif name == "synthesis" and payload:
                            logging.info(f"Processing synthesis task, payload type: {type(payload)}, length: {len(str(payload)) if payload else 0}")
                            draft_out = _load_model_output(payload, DraftOutput)
                            logging.info(f"Draft parsed successfully, final_answer length: {len(draft_out.draft.final_answer) if draft_out else 0}")
                        elif name == "critic" and payload:
                            critic_out = _load_model_output(payload, VerdictOutput)
                    except Exception as e:
                        # Parsing failure: leave as None; we'll fail-fast below.
                        logging.error(f"Failed to parse {name} output: {e}", exc_info=True)
                        pass

                evidence: list[EvidenceItem] = (web_out.evidence if web_out else [])[: self._config.max_fetches]
                sources = list(dict.fromkeys([e.url for e in evidence if e.url]))

                # Fail-fast on missing critical outputs.
                if plan_out is None or web_out is None:
                    tracer.end({"status": "FAILED", "reason": "missing planning/web outputs"})
                    return ChatResult(
                        session_id=session_id,
                        answer="",
                        sources=[],
                        agents_created=agents_created,
                        models_used=models_used,
                        execution_summary=execution,
                        run_id=trace.run_id,
                        trace_id=trace.trace_id,
                        status="FAILED",
                        hitl_required=False,
                    )

                # Evidence gate: if no evidence, require HITL.
                if not evidence:
                    token = str(uuid.uuid4())
                    self._store.set(session_id, "hitl_token", token)
                    self._store.set(session_id, "last_language", interp.input_language)
                    self._store.set(session_id, "last_sources", sources)
                    self._store.set(session_id, "last_evidence", [e.model_dump() for e in evidence])
                    tracer.end({"status": "NEEDS_HITL", "sources_count": 0, "evidence_count": 0})
                    return ChatResult(
                        session_id=session_id,
                        answer="",
                        sources=[],
                        agents_created=agents_created,
                        models_used=models_used,
                        execution_summary=execution,
                        run_id=trace.run_id,
                        trace_id=trace.trace_id,
                        status="NEEDS_HITL",
                        hitl_required=True,
                        hitl_token=token,
                        hitl_notes="No se encontró evidencia web suficiente. Aprueba para responder con conocimiento general (con limitaciones) o rechaza para devolver INSUFFICIENT_EVIDENCE.",
                    )

                # Fact-check / critic can still force insufficient evidence.
                verdict = None
                if critic_out is not None:
                    verdict = critic_out.verdict.status
                elif fact_out is not None:
                    verdict = fact_out.verdict.status

                if verdict == "INSUFFICIENT_EVIDENCE":
                    tracer.end({"status": "INSUFFICIENT_EVIDENCE", "sources_count": len(sources)})
                    return ChatResult(
                        session_id=session_id,
                        answer=self._insufficient(interp.input_language),
                        sources=sources,
                        agents_created=agents_created,
                        models_used=models_used,
                        execution_summary=execution,
                        run_id=trace.run_id,
                        trace_id=trace.trace_id,
                        status="INSUFFICIENT_EVIDENCE",
                        hitl_required=False,
                    )

                answer = (draft_out.draft.final_answer if draft_out else "").strip()
                if not answer:
                    tracer.end({"status": "FAILED", "reason": "empty final answer"})
                    return ChatResult(
                        session_id=session_id,
                        answer="",
                        sources=sources,
                        agents_created=agents_created,
                        models_used=models_used,
                        execution_summary=execution,
                        run_id=trace.run_id,
                        trace_id=trace.trace_id,
                        status="FAILED",
                        hitl_required=False,
                    )

                tracer.end(
                    {
                        "status": "SUCCESS",
                        "input_language": interp.input_language,
                        "sources_count": len(sources),
                        "evidence_count": len(evidence),
                        "answer_chars": len(answer),
                    }
                )
                return ChatResult(
                    session_id=session_id,
                    answer=answer,
                    sources=sources,
                    agents_created=agents_created,
                    models_used=models_used,
                    execution_summary=execution,
                    run_id=trace.run_id,
                    trace_id=trace.trace_id,
                    status="SUCCESS",
                    hitl_required=False,
                )
            except Exception as e:
                tracer.end({"status": "FAILED", "error": str(e)})
                execution.append({"name": "final", "status": "ERROR", "details": {"error": str(e)}})
                return ChatResult(
                    session_id=session_id,
                    answer="",
                    sources=[],
                    agents_created=self._store.get(session_id, "agents_created", []) or [],
                    models_used=self._store.get(session_id, "models_used", []) or [],
                    execution_summary=execution,
                    run_id=trace.run_id,
                    trace_id=trace.trace_id,
                    status="FAILED",
                    hitl_required=False,
                )

    def approve(self, cmd: ApproveCommand) -> ApproveResult:
        token = self._store.get(cmd.session_id, "hitl_token")
        sources = self._store.get(cmd.session_id, "last_sources", []) or []
        lang = self._store.get(cmd.session_id, "last_language", "en")
        execution = [{"name": "hitl", "status": "OK", "details": {"approved": cmd.approved}}]

        if not cmd.approved:
            return ApproveResult(
                session_id=cmd.session_id,
                answer=self._insufficient(lang),
                sources=sources,
                execution_summary=execution,
                status="INSUFFICIENT_EVIDENCE",
                hitl_required=False,
                hitl_token=token,
            )

        # Approved: answer from general knowledge (short, with limitations).
        answer = self._knowledge_answer(lang, cmd.notes or "")
        answer = answer + "\n\nLimitations:\n- Respuesta con aprobación humana y sin evidencia web suficiente."
        return ApproveResult(
            session_id=cmd.session_id,
            answer=answer,
            sources=sources,
            execution_summary=execution,
            status="SUCCESS" if sources else "INSUFFICIENT_EVIDENCE",
            hitl_required=False,
            hitl_token=token,
        )

    def _insufficient(self, lang: str) -> str:
        if lang == "es":
            return "INSUFFICIENT_EVIDENCE: No se encontró evidencia suficiente para responder con fuentes."
        if lang == "it":
            return "INSUFFICIENT_EVIDENCE: Non ci sono prove sufficienti per rispondere con fonti."
        return "INSUFFICIENT_EVIDENCE: Not enough evidence to answer with sources."

    def _knowledge_answer(self, lang: str, topic: str) -> str:
        # Deterministic fallback.
        if lang == "es":
            return f"Respuesta breve (conocimiento general): {topic}".strip()
        if lang == "it":
            return f"Risposta breve (conoscenza generale): {topic}".strip()
        return f"Short answer (general knowledge): {topic}".strip()

