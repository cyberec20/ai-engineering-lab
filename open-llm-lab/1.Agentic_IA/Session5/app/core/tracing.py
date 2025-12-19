from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Generator, Optional

from app.core.config import AppConfig, load_langfuse_env, load_langsmith_env


@dataclass(frozen=True)
class TraceContext:
    run_id: str | None
    trace_id: str | None
    started_at: str


class TraceSpan:
    def __init__(self, end_fn) -> None:  # type: ignore[no-untyped-def]
        self._end_fn = end_fn
        self._ended = False
        self._outputs: dict[str, Any] | None = None

    def set_outputs(self, outputs: dict[str, Any]) -> None:
        self._outputs = outputs

    def end(self, outputs: dict[str, Any] | None = None) -> None:
        if self._ended:
            return
        self._ended = True
        self._end_fn(outputs or self._outputs or {})

    def __enter__(self) -> "TraceSpan":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        if self._ended:
            return
        if exc is not None:
            self.end({"error": str(exc)})
            return
        self.end(self._outputs or {"ok": True})


class TraceSession:
    def __init__(self, provider: str, root) -> None:  # type: ignore[no-untyped-def]
        self.provider = provider
        self._root = root
        self._lf = None
        self._ended = False

    def set_langfuse_client(self, client) -> None:  # type: ignore[no-untyped-def]
        self._lf = client

    def span(self, name: str, inputs: dict[str, Any]) -> TraceSpan:
        if self.provider == "langsmith" and self._root is not None:
            child = self._root.create_child(name=name, run_type="chain", inputs=inputs)
            child.post()

            def _end(outputs: dict[str, Any]) -> None:
                child.end(outputs=outputs)
                child.patch()

            return TraceSpan(_end)

        if self.provider == "langfuse" and self._root is not None:
            obs = self._root.span(name=name, input=inputs)

            def _end(outputs: dict[str, Any]) -> None:
                obs.end(output=outputs)

            return TraceSpan(_end)

        return TraceSpan(lambda _o: None)

    def end(self, outputs: dict[str, Any]) -> None:
        if self._ended:
            return
        self._ended = True
        if self.provider == "langsmith" and self._root is not None:
            self._root.end(outputs=outputs)
            self._root.patch()
        elif self.provider == "langfuse" and self._root is not None:
            self._root.update(output=outputs)
            if self._lf is not None:
                try:
                    self._lf.flush()
                except Exception:
                    pass


def _build_langsmith_root(name: str, inputs: dict[str, Any]) -> tuple[Optional[str], Optional[object]]:
    env = load_langsmith_env()
    if not env.enabled or not env.api_key:
        return None, None
    from langsmith import Client as LangSmithClient  # local import
    from langsmith.run_trees import RunTree  # local import

    client = LangSmithClient(api_url=env.endpoint, api_key=env.api_key)
    root = RunTree(
        name=name,
        run_type="chain",
        inputs=inputs,
        project_name=env.project or "Session5",
        client=client,
    )
    root.post()
    return str(root.id), root


def _build_langfuse_root(name: str, inputs: dict[str, Any]) -> tuple[Optional[str], Optional[object], Optional[object]]:
    env = load_langfuse_env()
    if not env.enabled or not env.public_key or not env.secret_key or not env.base_url:
        return None, None, None
    from langfuse import Langfuse  # type: ignore

    lf = Langfuse(public_key=env.public_key, secret_key=env.secret_key, host=env.base_url)
    trace = lf.trace(name=name, input=inputs)
    return getattr(trace, "id", None), trace, lf


@contextmanager
def traced_root_run(
    *,
    config: AppConfig,
    name: str,
    inputs: dict[str, Any],
) -> Generator[tuple[TraceContext, TraceSession], None, None]:
    started_at = datetime.now(timezone.utc).isoformat()

    if config.trace_provider == "langsmith":
        run_id, root = _build_langsmith_root(name, inputs)
        session = TraceSession("langsmith", root)
        trace = TraceContext(run_id=run_id, trace_id=run_id, started_at=started_at)
    elif config.trace_provider == "langfuse":
        trace_id, root, lf = _build_langfuse_root(name, inputs)
        session = TraceSession("langfuse", root)
        if lf is not None:
            session.set_langfuse_client(lf)
        trace = TraceContext(run_id=trace_id, trace_id=trace_id, started_at=started_at)
    else:
        session = TraceSession("none", None)
        trace = TraceContext(run_id=None, trace_id=None, started_at=started_at)

    try:
        yield trace, session
    finally:
        session.end(outputs={"ok": True})
