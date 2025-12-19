from __future__ import annotations

import re

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
import json

from app.core.config import AppConfig
from app.orchestrator.graphs.research_operator import GraphDeps, build_research_operator_graph


class DummyTracer:
    def start_run(self, *, name: str, run_id: str, trace_id: str, inputs: dict, metadata: dict) -> None:
        return None

    def end_run(self, *, outputs: dict | None = None, error: str | None = None) -> None:
        return None

    def start_span(self, *, name: str, span_id: str, inputs: dict | None = None, metadata: dict | None = None) -> None:
        return None

    def end_span(
        self,
        *,
        span_id: str,
        outputs: dict | None = None,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        return None

    def event(self, *, name: str, payload: dict | None = None) -> None:
        return None


class StubWeb:
    def web_search(self, query: str):
        return [
            type(
                "R",
                (),
                {
                    "title": "Example Title",
                    "url": "https://example.com/a",
                    "snippet": "Python supports type hints and typing.",
                },
            )()
        ]

    def web_fetch(self, url: str):
        return type(
            "F",
            (),
            {
                "url": url,
                "title": "Example Page",
                "text": "Python supports type hints via the typing module and PEP 484.",
                "content_type": "text/html",
                "fetched_at": "2025-01-01T00:00:00Z",
            },
        )()


class StubLLMs:
    def __init__(self, *, mode: str):
        self.mode = mode

    def chat(self, role: str, *, system: str, user: str, json_mode: bool = False) -> str:
        if role == "planner":
            return '{"plan":["Search web","Synthesize answer"],"queries":["python type hints PEP 484"]}'

        if role == "synthesizer":
            m = re.search(r"snippet_id=([a-f0-9\\-]{8,})\\s+url=(\\S+)", user)
            snippet_id = m.group(1) if m else "missing-snippet"
            url = m.group(2) if m else "https://example.com/a"
            if self.mode == "hitl":
                snippet_id = "missing-snippet"
            payload = {
                "question": "What are Python type hints?",
                "key_points": [
                    {
                        "id": "kp1",
                        "claim": "Python supports type hints via typing (PEP 484).",
                        "citations": [{"url": url, "snippet_id": snippet_id}],
                        "confidence": 0.8,
                    }
                ],
                "final_answer": "Python type hints are optional annotations for variables and functions, standardized by PEP 484.",
                "limitations": ["Evidence is limited to the provided snippets."],
                "followups": ["Which tooling supports type checking?"],
            }
            return json.dumps(payload)

        if role == "guard":
            if self.mode == "hitl":
                return '{"supported":false,"missing_point_ids":["kp1"],"rationale":"Missing snippet evidence."}'
            return '{"supported":true,"missing_point_ids":[],"rationale":"Citations match snippets."}'

        if role == "reflector":
            return "Looks clear."

        raise AssertionError(f"Unexpected role: {role}")


def _base_config(max_iterations: int) -> AppConfig:
    return AppConfig(
        host="127.0.0.1",
        port=8100,
        ollama_base_url="http://127.0.0.1:11434",
        request_timeout_seconds=5,
        max_iterations=max_iterations,
        trace_provider="none",
        graph_mode="full",
        web_max_results=4,
        web_max_queries=3,
        web_fetches_per_query=1,
        web_min_delay_seconds=0.0,
        web_cache_ttl_seconds=0,
        web_cache_max_entries=0,
        enable_llm_planner=True,
        enable_llm_synthesizer=True,
        enable_llm_guard_rationale=False,
        enable_llm_reflector=False,
        translation_retries=1,
        model_planner="qwen3:8b",
        model_researcher="deepseek-r1:8b",
        model_synthesizer="ministral-3:8b",
        model_guard="llama3.1:8b",
        model_reflector="deepseek-r1:8b",
    )


def test_smoke_success_path_executes_guard():
    cfg = _base_config(max_iterations=1)
    deps = GraphDeps(config=cfg, llms=StubLLMs(mode="success"), web=StubWeb(), tracer=DummyTracer())
    builder = build_research_operator_graph(deps)
    graph = builder.compile(checkpointer=InMemorySaver())

    state = {
        "user_message": "What are Python type hints?",
        "iteration_count": 0,
        "hitl_required": False,
        "hitl_notes": None,
        "guard_executed": False,
        "run_id": "run-1",
        "trace_id": "run-1",
        "timestamps": {},
        "execution_summary": [],
        "snippets": {},
    }
    out = graph.invoke(state, {"configurable": {"thread_id": "s1"}})

    assert out["guard_executed"] is True
    assert out.get("status") in {"SUCCESS", "FAILED", "NEEDS_HITL"}
    assert any(s.get("name") == "anti_hallucination_guard" for s in out.get("execution_summary", []))
    assert out.get("final_answer")


def test_smoke_hitl_pause_and_resume():
    cfg = _base_config(max_iterations=0)
    deps = GraphDeps(config=cfg, llms=StubLLMs(mode="hitl"), web=StubWeb(), tracer=DummyTracer())
    builder = build_research_operator_graph(deps)
    graph = builder.compile(checkpointer=InMemorySaver())

    init = {
        "user_message": "What are Python type hints?",
        "iteration_count": 0,
        "hitl_required": False,
        "hitl_notes": None,
        "guard_executed": False,
        "run_id": "run-2",
        "trace_id": "run-2",
        "timestamps": {},
        "execution_summary": [],
        "snippets": {},
    }
    config = {"configurable": {"thread_id": "s2"}}

    interrupt_id = None
    for chunk in graph.stream(init, config):
        if "__interrupt__" in chunk:
            interrupt_id = chunk["__interrupt__"][0].id
            break

    assert interrupt_id is not None
    snap = graph.get_state(config).values
    assert snap["guard_executed"] is True
    assert snap["status"] == "NEEDS_HITL"

    for _ in graph.stream(Command(resume={interrupt_id: {"approved": True, "notes": "OK"}}), config):
        pass

    out = graph.get_state(config).values
    assert out["status"] == "SUCCESS"
    assert out.get("final_answer")
