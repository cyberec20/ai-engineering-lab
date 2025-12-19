from __future__ import annotations

from app.core.config import AppConfig
from app.orchestrator.observability.langfuse_adapter import LangfuseAdapter
from app.orchestrator.observability.langsmith_adapter import LangSmithAdapter
from app.orchestrator.observability.noop import NoopTraceAdapter


class TraceManager:
    """
    Keep per-run adapter instances in memory so HITL resumption can continue
    the same trace/run until the graph reaches final.
    """

    def __init__(self, config: AppConfig):
        self._provider = config.trace_provider
        self._runs: dict[str, object] = {}

    def _new_adapter(self):
        # NOTE: For LangSmith we rely on native LangChain/LangGraph tracing (callbacks + env vars).
        # The custom LangSmithAdapter is kept for reference/debugging but is intentionally not used here.
        if self._provider == "langsmith":
            return NoopTraceAdapter()
        # NOTE: For Langfuse we rely on native LangChain callback handler (callbacks + env vars).
        # The custom LangfuseAdapter remains for reference/debugging but is intentionally not used here.
        if self._provider == "langfuse":
            return NoopTraceAdapter()
        return NoopTraceAdapter()

    def start_run(self, *, name: str, run_id: str, trace_id: str, inputs: dict, metadata: dict) -> dict:
        adapter = self._new_adapter()
        adapter.start_run(name=name, run_id=run_id, trace_id=trace_id, inputs=inputs, metadata=metadata)
        self._runs[run_id] = adapter
        return adapter.provider_ids

    def end_run(self, *, run_id: str, outputs: dict | None = None, error: str | None = None) -> None:
        adapter = self._runs.get(run_id)
        if not adapter:
            return None
        adapter.end_run(outputs=outputs, error=error)
        self._runs.pop(run_id, None)

    def start_span(self, *, name: str, span_id: str, inputs: dict | None = None, metadata: dict | None = None) -> None:
        run_id = (metadata or {}).get("run_id")
        if not run_id:
            return None
        adapter = self._runs.get(run_id)
        if not adapter:
            return None
        adapter.start_span(name=name, span_id=span_id, inputs=inputs, metadata=metadata)

    def end_span(
        self,
        *,
        span_id: str,
        outputs: dict | None = None,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        run_id = (metadata or {}).get("run_id")
        if not run_id:
            return None
        adapter = self._runs.get(run_id)
        if not adapter:
            return None
        adapter.end_span(span_id=span_id, outputs=outputs, error=error, metadata=metadata)

    def event(self, *, name: str, payload: dict | None = None, metadata: dict | None = None) -> None:
        run_id = (metadata or {}).get("run_id")
        if not run_id:
            return None
        adapter = self._runs.get(run_id)
        if not adapter:
            return None
        adapter.event(name=name, payload=payload)


def get_trace_manager(config: AppConfig) -> TraceManager:
    return TraceManager(config)
