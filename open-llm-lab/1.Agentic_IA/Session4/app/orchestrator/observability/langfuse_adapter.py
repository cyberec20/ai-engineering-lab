from __future__ import annotations

from langfuse import Langfuse

from app.core.config import load_langfuse_env
from app.orchestrator.observability.adapter import ProviderIds, TraceAdapter


class LangfuseAdapter(TraceAdapter):
    def __init__(self):
        env = load_langfuse_env()
        self._client = None
        self._trace_id: str | None = None
        self._root_span = None
        self._spans: dict[str, object] = {}
        self._ids = ProviderIds()

        if env.enabled:
            try:
                self._client = Langfuse(
                    public_key=env.public_key,
                    secret_key=env.secret_key,
                    base_url=env.base_url,
                    host=env.base_url,
                    tracing_enabled=True,
                )
            except Exception:
                self._client = None

    def start_run(self, *, name: str, run_id: str, trace_id: str, inputs: dict, metadata: dict) -> None:
        if not self._client:
            return None
        try:
            self._trace_id = self._client.create_trace_id()
            self._ids = ProviderIds(langfuse_trace_id=self._trace_id)
            self._root_span = self._client.start_span(
                trace_context={"trace_id": self._trace_id},
                name=name,
                input=inputs or {},
                metadata=metadata or {},
            )
        except Exception:
            self._trace_id = None
            self._root_span = None

    def end_run(self, *, outputs: dict | None = None, error: str | None = None) -> None:
        if not self._client or not self._root_span:
            return None
        try:
            if outputs is not None:
                self._root_span.update(output=outputs)
            if error:
                self._root_span.update(level="ERROR", status_message=error)
            self._root_span.end()
            self._client.flush()
        except Exception:
            return None

    def start_span(self, *, name: str, span_id: str, inputs: dict | None = None, metadata: dict | None = None) -> None:
        if not self._client or not self._trace_id:
            return None
        try:
            span = self._client.start_span(
                trace_context={"trace_id": self._trace_id},
                name=name,
                input=inputs or {},
                metadata=metadata or {},
            )
            self._spans[span_id] = span
        except Exception:
            return None

    def end_span(
        self,
        *,
        span_id: str,
        outputs: dict | None = None,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        span = self._spans.get(span_id)
        if not span:
            return None
        try:
            if outputs is not None:
                span.update(output=outputs)
            if metadata is not None:
                span.update(metadata=metadata)
            if error:
                span.update(level="ERROR", status_message=error)
            span.end()
        except Exception:
            return None

    def event(self, *, name: str, payload: dict | None = None) -> None:
        if not self._client or not self._trace_id:
            return None
        try:
            self._client.create_event(
                trace_context={"trace_id": self._trace_id},
                name=name,
                input=payload or {},
            )
        except Exception:
            return None

    @property
    def provider_ids(self) -> dict:
        return {"langsmith_run_id": None, "langfuse_trace_id": self._ids.langfuse_trace_id}

