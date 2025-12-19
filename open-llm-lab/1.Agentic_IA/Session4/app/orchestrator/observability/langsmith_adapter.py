from __future__ import annotations

import os
import sys
import time
import datetime as _dt
import uuid as _uuid
from typing import Any

from langsmith import Client

from app.core.config import load_langsmith_env
from app.orchestrator.observability.adapter import ProviderIds, TraceAdapter


class LangSmithAdapter(TraceAdapter):
    def __init__(self):
        self._env = load_langsmith_env()
        self._client = None
        self._root_id: str | None = None
        self._spans: set[str] = set()
        self._ids = ProviderIds()

        if self._env.enabled and self._env.api_key:
            # Use official SDK knobs to avoid "Pending" runs:
            # - auto_batch_tracing=False: avoid background batching that can delay end_time PATCH
            # - tracing_sampling_rate=None: disable sampling filter so update_run doesn't require trace_id
            self._client = Client(
                api_key=self._env.api_key,
                api_url=self._env.endpoint,
                auto_batch_tracing=False,
                tracing_sampling_rate=None,
            )

            self._debug(
                "client configured ("
                f"api_url={self._env.endpoint}, project={self._env.project}, "
                f"auto_batch_tracing={getattr(self._client, 'auto_batch_tracing', None)}, "
                f"tracing_sampling_rate={getattr(self._client, 'tracing_sampling_rate', None)}, "
                f"tracing_sample_rate={getattr(self._client, 'tracing_sample_rate', None)}"
                ")"
            )

    def _debug(self, msg: str) -> None:
        if os.getenv("TRACE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
            print(f"[LangSmithAdapter] {msg}", file=sys.stderr, flush=True)

    def _now(self) -> _dt.datetime:
        return _dt.datetime.now(_dt.timezone.utc)

    def _as_id(self, value: str | None) -> str | None:
        """
        Always return a canonical string UUID when possible.

        Some LangSmith SDK versions can fail if you pass uuid.UUID objects into update_run/create_run.
        Using strings avoids the "one of the hex, bytes..." UUID construction error and prevents Pending runs.
        """
        if not value:
            return value
        try:
            return str(_uuid.UUID(str(value)))
        except Exception:
            return str(value)

    def _retry(self, fn, *, attempts: int = 3) -> bool:
        delay = 0.25
        for i in range(1, attempts + 1):
            try:
                fn()
                return True
            except Exception as e:
                msg = str(e)
                self._debug(f"request failed (attempt {i}/{attempts}) [{type(e).__name__}]: {msg}")
                # Fail-fast: this error is not transient/network; it's a type/ID issue.
                if "one of the hex" in msg or "bytes_le" in msg:
                    return False
                if i < attempts:
                    time.sleep(delay)
                    delay = min(delay * 2.0, 2.0)
        return False

    def _maybe_flush(self) -> None:
        """
        Use the official SDK flush to force sending any buffered operations.
        Even with auto_batch_tracing=False, flush() is safe and removes guesswork.
        """
        if not self._client:
            return
        try:
            self._client.flush()
        except Exception as e:
            self._debug(f"flush failed: {e}")

    def start_run(self, *, name: str, run_id: str, trace_id: str, inputs: dict, metadata: dict) -> None:
        if not self._client:
            return None
        self._root_id = trace_id or run_id
        root_id = self._as_id(self._root_id)
        payload_extra = {"metadata": metadata or {}}
        ok = self._retry(
            lambda: self._client.create_run(
                id=root_id,
                project_name=self._env.project,
                name=name,
                run_type="chain",
                inputs=inputs or {},
                start_time=self._now(),
                extra=payload_extra,
            )
        )
        self._maybe_flush()
        if not ok:
            self._debug("start_run failed; tracing disabled for this run")
            self._root_id = None
            return None
        self._ids = ProviderIds(langsmith_run_id=str(self._root_id))
        self._debug(f"start_run ok (run_id={self._root_id})")

    def end_run(self, *, outputs: dict | None = None, error: str | None = None) -> None:
        if not self._client or not self._root_id:
            return None
        root_id = self._as_id(self._root_id)

        # Best-effort: close any spans we still track.
        for sid in list(self._spans):
            sid_id = self._as_id(sid)
            self._retry(
                lambda sid=sid: self._client.update_run(
                    sid_id,
                    end_time=self._now(),
                    error="force_closed",
                ),
                attempts=8,
            )
            self._spans.discard(sid)

        ok = self._retry(
            lambda: self._client.update_run(
                root_id,
                end_time=self._now(),
                outputs=outputs or None,
                error=error or None,
            ),
            attempts=8,
        )
        self._maybe_flush()
        if not ok:
            self._debug(f"end_run failed; run may remain Pending (run_id={self._root_id})")
        else:
            self._debug(f"end_run ok (run_id={self._root_id})")
            # In debug mode, verify the run is actually closed on the server.
            if os.getenv("TRACE_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}:
                try:
                    # The backend can be eventually consistent; poll briefly.
                    end_time = None
                    out_keys = None
                    for _ in range(8):
                        time.sleep(0.25)
                        self._maybe_flush()
                        run = self._client.read_run(root_id)
                        end_time = getattr(run, "end_time", None)
                        out = getattr(run, "outputs", None)
                        out_keys = list(out.keys()) if isinstance(out, dict) else None
                        if end_time:
                            break
                    self._debug(f"server_run end_time={end_time} outputs_keys={out_keys}")
                    if not end_time:
                        # Log a compact snapshot for troubleshooting without dumping everything.
                        self._debug(
                            "server_run still open after polling; this suggests the end update is not being applied."
                        )
                except Exception as e:
                    self._debug(f"read_run verify failed: {e}")
        self._root_id = None

    def start_span(self, *, name: str, span_id: str, inputs: dict | None = None, metadata: dict | None = None) -> None:
        if not self._client or not self._root_id:
            return None
        payload_extra = {"metadata": metadata or {}}
        root_id = self._as_id(self._root_id)
        span_id_obj = self._as_id(span_id)
        ok = self._retry(
            lambda: self._client.create_run(
                id=span_id_obj,
                project_name=self._env.project,
                name=name,
                run_type="chain",
                inputs=inputs or {},
                start_time=self._now(),
                parent_run_id=root_id,
                extra=payload_extra,
            )
        )
        self._maybe_flush()
        if ok:
            self._spans.add(span_id)
        else:
            self._debug(f"start_span failed (span_id={span_id})")

    def end_span(
        self,
        *,
        span_id: str,
        outputs: dict | None = None,
        error: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        if not self._client or span_id not in self._spans:
            return None
        span_id_obj = self._as_id(span_id)
        ok = self._retry(
            lambda: self._client.update_run(
                span_id_obj,
                end_time=self._now(),
                outputs=outputs or None,
                error=error or None,
            ),
            attempts=8,
        )
        self._maybe_flush()
        if not ok:
            self._debug(f"end_span failed; span may remain Pending (span_id={span_id})")
        self._spans.discard(span_id)

    def event(self, *, name: str, payload: dict | None = None) -> None:
        if not self._client or not self._root_id:
            return None
        events = [{"name": name, "time": None, "kwargs": {"payload": payload or {}}}]
        root_id = self._as_id(self._root_id)
        self._retry(lambda: self._client.update_run(root_id, events=events), attempts=1)

    @property
    def provider_ids(self) -> dict:
        return {"langsmith_run_id": self._ids.langsmith_run_id, "langfuse_trace_id": None}
