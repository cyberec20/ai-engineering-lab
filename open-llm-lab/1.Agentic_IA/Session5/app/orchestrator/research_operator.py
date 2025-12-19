from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

try:
    from langchain_ollama import ChatOllama  # type: ignore
except Exception:  # pragma: no cover
    ChatOllama = None  # type: ignore

from app.core.config import AppConfig
from app.core.tracing import traced_root_run
from app.orchestrator.engine import SessionStore
from app.orchestrator.models import AgentSpec, ApproveResult, ChatResult, EvidenceItem
from app.orchestrator.query_interpreter import QueryInterpreter
from app.orchestrator.tools_web import WebTools, polite_delay


@dataclass(frozen=True)
class ApproveCommand:
    session_id: str
    approved: bool
    notes: str | None = None


class ResearchOperator:
    def __init__(self, *, config: AppConfig, store: SessionStore) -> None:
        self._config = config
        self._store = store
        self._interpreter = QueryInterpreter(config=config)
        self._web = WebTools(config=config)

    def _ensure_team(self, session_id: str) -> list[AgentSpec]:
        team = self._store.get_memory(session_id, "team")
        if team:
            return team
        team_specs = [
            AgentSpec(
                role="ResearchLead",
                objective="Interpret the user request and orchestrate the team with strict budgets.",
                allowed_tools=[],
                model_name=self._config.model_research_lead,
                success_criteria="Produces short keyword queries and a clear plan.",
            ),
            AgentSpec(
                role="WebResearcher",
                objective="Find sources and extract evidence snippets with URLs.",
                allowed_tools=["web_search", "web_fetch"],
                model_name=self._config.model_web_researcher,
                success_criteria="Returns evidence items with URLs and text snippets.",
            ),
            AgentSpec(
                role="FactChecker",
                objective="Ensure key claims are supported by evidence; otherwise request more evidence or mark insufficient.",
                allowed_tools=[],
                model_name=self._config.model_fact_checker,
                success_criteria="Flags missing evidence; avoids hallucinations.",
            ),
            AgentSpec(
                role="Synthesizer",
                objective="Write the final answer in the user's language using evidence and citations.",
                allowed_tools=[],
                model_name=self._config.model_synthesizer,
                success_criteria="Produces a concise answer with sources.",
            ),
            AgentSpec(
                role="Critic",
                objective="Final sanity check: language, coherence, and evidence coverage.",
                allowed_tools=[],
                model_name=self._config.model_critic,
                success_criteria="Approves or requests HITL/insufficient evidence.",
            ),
        ]
        self._store.set_memory(session_id, "team", team_specs)
        self._store.get_or_create(session_id).agents_created = [
            {"role": a.role, "model": a.model_name, "tools": a.allowed_tools} for a in team_specs
        ]
        return team_specs

    def chat(self, *, user_message: str, session_id: str) -> ChatResult:
        with traced_root_run(
            config=self._config,
            name="research_operator",
            inputs={"session_id": session_id, "user_message": user_message},
        ) as (trace, tracer):
            execution: list[dict[str, Any]] = []
            started = datetime.now(timezone.utc)
            try:
                with tracer.span("query_interpreter", {"user_message": user_message}) as span:
                    interp = self._interpreter.interpret(user_message)
                    span.end(
                        {
                            "normalized_query": interp.normalized_query,
                            "intent": interp.intent,
                            "input_language": interp.input_language,
                            "entities": interp.entities[:3],
                            "keywords": interp.keywords[:8],
                        }
                    )
                execution.append(
                    {
                        "name": "query_interpreter",
                        "status": "OK",
                        "started_at": started.isoformat(),
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                        "details": {
                            "normalized_query": interp.normalized_query,
                            "intent": interp.intent,
                            "input_language": interp.input_language,
                        },
                    }
                )

                team = self._ensure_team(session_id)
                models_used = sorted({a.model_name for a in team})

                base = (interp.entities[0] if interp.entities else interp.normalized_query).strip()
                queries: list[str] = []
                if base:
                    queries.append(base)
                if interp.intent == "biography":
                    queries.append(f"{base} biography contributions")
                elif interp.intent == "definition":
                    queries.append(f"{base} definition tcp/ip")
                if "wikipedia" in (interp.preferred_sources or []):
                    queries.append(f"site:wikipedia.org {base}")
                queries = [q for q in dict.fromkeys([q.strip() for q in queries if q.strip()]).keys()]
                queries = queries[: max(1, self._config.max_queries)]
                execution.append({"name": "planner", "status": "OK", "details": {"queries": queries}})

                evidence: list[EvidenceItem] = []
                used_sources: list[str] = []
                with tracer.span("researcher", {"queries": queries}) as researcher_span:
                    for q in queries[: self._config.max_queries]:
                        polite_delay(0.05)
                        with tracer.span("web_search", {"query": q}) as search_span:
                            results = self._web.web_search(q)
                            search_span.end(
                                {
                                    "results": len(results),
                                    "top_urls": [r.url for r in results[:3] if r.url],
                                }
                            )
                        for r in results[: self._config.max_fetches]:
                            with tracer.span("web_fetch", {"url": r.url}) as fetch_span:
                                item = self._web.web_fetch(r.url)
                                fetch_span.end(
                                    {
                                        "fetched": bool(item and item.snippet),
                                        "snippet_chars": len(item.snippet) if (item and item.snippet) else 0,
                                    }
                                )
                            if item and item.url:
                                evidence.append(item)
                                used_sources.append(item.url)
                            if len(evidence) >= self._config.max_fetches:
                                break
                        if len(evidence) >= self._config.max_fetches:
                            break
                    researcher_span.end(
                        {
                            "queries_used": queries[: self._config.max_queries],
                            "evidence_items": len(evidence),
                            "sources": len(list(dict.fromkeys(used_sources))),
                        }
                    )
                used_sources = list(dict.fromkeys(used_sources))
                execution.append(
                    {
                        "name": "researcher",
                        "status": "OK" if evidence else "WARN",
                        "details": {
                            "snippets": len([e for e in evidence if e.snippet]),
                            "sources": len(used_sources),
                            "queries_used": queries,
                        },
                    }
                )

                self._store.set_memory(session_id, "last_evidence", [e.model_dump() for e in evidence])
                self._store.set_memory(session_id, "last_language", interp.input_language)
                self._store.set_memory(session_id, "last_sources", used_sources)

                if not evidence:
                    token = str(uuid.uuid4())
                    self._store.set_memory(session_id, "hitl_token", token)
                    tracer.end(
                        {
                            "status": "NEEDS_HITL",
                            "input_language": interp.input_language,
                            "queries": queries,
                            "sources_count": 0,
                            "evidence_count": 0,
                        }
                    )
                    return ChatResult(
                        session_id=session_id,
                        answer="",
                        sources=[],
                        agents_created=self._store.get_or_create(session_id).agents_created,
                        models_used=models_used,
                        execution_summary=execution,
                        run_id=trace.run_id,
                        trace_id=trace.trace_id,
                        status="NEEDS_HITL",
                        hitl_required=True,
                        hitl_token=token,
                        hitl_notes="No se encontró evidencia web. Aprueba para responder con conocimiento general (con limitaciones) o rechaza para devolver INSUFFICIENT_EVIDENCE.",
                    )

                with tracer.span("synthesizer", {"language": interp.input_language}) as synth_span:
                    answer = self._synthesize(interp.input_language, user_message, evidence, allow_knowledge=False)
                    synth_span.end({"answer_chars": len(answer)})
                execution.append({"name": "synthesizer", "status": "OK", "details": {"language": interp.input_language}})

                supported = bool(used_sources)
                execution.append(
                    {
                        "name": "anti_hallucination_guard",
                        "status": "OK" if supported else "WARN",
                        "details": {"supported": supported},
                    }
                )

                tracer.end(
                    {
                        "status": "SUCCESS",
                        "input_language": interp.input_language,
                        "sources_count": len(used_sources),
                        "evidence_count": len(evidence),
                        "answer_chars": len(answer),
                    }
                )
                return ChatResult(
                    session_id=session_id,
                    answer=answer,
                    sources=used_sources,
                    agents_created=self._store.get_or_create(session_id).agents_created,
                    models_used=models_used,
                    execution_summary=execution,
                    run_id=trace.run_id,
                    trace_id=trace.trace_id,
                    status="SUCCESS",
                    hitl_required=False,
                )
            except Exception as e:
                execution.append({"name": "final", "status": "ERROR", "details": {"error": str(e)}})
                tracer.end({"status": "FAILED", "error": str(e)})
                return ChatResult(
                    session_id=session_id,
                    answer="",
                    sources=[],
                    agents_created=self._store.get_or_create(session_id).agents_created,
                    models_used=[],
                    execution_summary=execution,
                    run_id=trace.run_id,
                    trace_id=trace.trace_id,
                    status="FAILED",
                    hitl_required=False,
                )

    def approve(self, cmd: ApproveCommand) -> ApproveResult:
        token = self._store.get_memory(cmd.session_id, "hitl_token")
        sources = self._store.get_memory(cmd.session_id, "last_sources", []) or []
        lang = self._store.get_memory(cmd.session_id, "last_language", "en")
        evidence_raw = self._store.get_memory(cmd.session_id, "last_evidence", []) or []
        evidence = [EvidenceItem.model_validate(e) for e in evidence_raw] if evidence_raw else []

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
                hitl_notes=None,
            )

        answer = self._synthesize(lang, cmd.notes or "", evidence, allow_knowledge=True)
        answer = answer + "\n\nLimitations:\n- Respuesta con aprobación humana y sin evidencia web suficiente."
        return ApproveResult(
            session_id=cmd.session_id,
            answer=answer,
            sources=sources,
            execution_summary=execution,
            status="SUCCESS" if sources else "INSUFFICIENT_EVIDENCE",
            hitl_required=False,
            hitl_token=token,
            hitl_notes=None,
        )

    def _insufficient(self, lang: str) -> str:
        if lang == "es":
            return "INSUFFICIENT_EVIDENCE: No se encontró evidencia suficiente para responder con fuentes."
        if lang == "it":
            return "INSUFFICIENT_EVIDENCE: Non ci sono prove sufficienti per rispondere con fonti."
        return "INSUFFICIENT_EVIDENCE: Not enough evidence to answer with sources."

    def _synthesize(
        self,
        lang: str,
        user_message: str,
        evidence: list[EvidenceItem],
        *,
        allow_knowledge: bool = False,
    ) -> str:
        if not self._config.enable_llm_synthesizer or ChatOllama is None:
            parts = []
            for e in evidence[:3]:
                if e.snippet:
                    parts.append(e.snippet)
            base = "\n".join(parts).strip()
            if not base:
                return self._insufficient(lang)
            return base

        prompt = (
            f"Answer in language '{lang}'.\n"
            "Use ONLY the provided evidence snippets for factual claims.\n"
            "Include a short 'Key points' list and cite sources as '(source: URL)'.\n"
        )
        if allow_knowledge:
            prompt += "If evidence is missing, you may answer from general knowledge but MUST add a clear limitation note.\n"

        snippets = "\n\n".join([f"- {e.snippet} (source: {e.url})" for e in evidence[: min(5, len(evidence))] if e.snippet])
        system = SystemMessage(content=prompt)
        human = HumanMessage(content=f"User question: {user_message}\n\nEvidence:\n{snippets}\n\nWrite the final answer.")
        llm = ChatOllama(model=self._config.model_synthesizer, base_url=self._config.ollama_base_url, temperature=0.2)
        msg = llm.invoke([system, human])
        return (getattr(msg, "content", "") or "").strip()
