from __future__ import annotations

from app.orchestrator.observability.adapter import ProviderIds, TraceAdapter


class NoopTraceAdapter(TraceAdapter):
    def __init__(self):
        self._ids = ProviderIds()

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

    @property
    def provider_ids(self) -> dict:
        return {"langsmith_run_id": None, "langfuse_trace_id": None}

