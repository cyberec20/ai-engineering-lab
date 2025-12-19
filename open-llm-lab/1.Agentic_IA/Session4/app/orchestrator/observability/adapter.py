from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class TraceAdapter:
    def start_run(self, *, name: str, run_id: str, trace_id: str, inputs: dict, metadata: dict) -> None:
        raise NotImplementedError

    def end_run(self, *, outputs: dict | None = None, error: str | None = None) -> None:
        raise NotImplementedError

    def start_span(
        self,
        *,
        name: str,
        span_id: str,
        inputs: dict | None = None,
        metadata: dict | None = None,
    ) -> None:
        raise NotImplementedError

    def end_span(
        self,
        *,
        span_id: str,
        outputs: dict | None = None,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        raise NotImplementedError

    def event(self, *, name: str, payload: dict | None = None) -> None:
        raise NotImplementedError

    @property
    def provider_ids(self) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class ProviderIds:
    langsmith_run_id: Optional[str] = None
    langfuse_trace_id: Optional[str] = None

