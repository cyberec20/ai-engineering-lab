from __future__ import annotations

import os
import time
import uuid

import pytest
from langsmith.utils import LangSmithNotFoundError

from app.core.config import load_config
from app.core.config import load_langsmith_env
from app.orchestrator.observability.langsmith_adapter import LangSmithAdapter


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


@pytest.mark.integration
def test_langsmith_run_closes_end_time_is_persisted():
    """
    Integration smoke test (opt-in).

    Validates the real failure mode we saw in practice:
    a run appears in LangSmith but remains Pending (end_time is never applied).

    How to run (from Session4/):
      set RUN_LANGSMITH_SMOKE=1
      pytest -q tests/test_langsmith_integration.py
    """
    if not _truthy(os.getenv("RUN_LANGSMITH_SMOKE")):
        pytest.skip("Set RUN_LANGSMITH_SMOKE=1 to run LangSmith integration smoke test.")

    # Ensure Session4/.env is loaded (tests may run without importing app.main).
    _ = load_config()

    # Keep smoke runs isolated (avoid polluting the main project).
    os.environ.setdefault("LANGCHAIN_PROJECT", "Session4-Smoke")
    os.environ.setdefault("LANGSMITH_PROJECT", os.environ["LANGCHAIN_PROJECT"])

    env = load_langsmith_env()
    if not env.api_key or not env.endpoint:
        pytest.skip("LangSmith API is not configured (missing LANGCHAIN_API_KEY or endpoint).")

    adapter = LangSmithAdapter()
    if not getattr(adapter, "_client", None):
        pytest.skip("LangSmithAdapter client is not enabled; check TRACE_PROVIDER and API key.")

    run_id = str(uuid.uuid4())
    trace_id = run_id
    adapter.start_run(name="research_operator_smoke", run_id=run_id, trace_id=trace_id, inputs={"ping": True}, metadata={"smoke": True})

    # Create at least one span to cover child-run closure too.
    span_id = str(uuid.uuid4())
    adapter.start_span(name="smoke_span", span_id=span_id, inputs={"step": 1}, metadata={"smoke": True, "run_id": run_id})
    adapter.end_span(span_id=span_id, outputs={"ok": True}, metadata={"smoke": True, "run_id": run_id})

    adapter.end_run(outputs={"status": "SUCCESS", "smoke": True})

    # Verify via the SDK that LangSmith sees an end_time (i.e., not Pending).
    # Poll because the backend can be eventually consistent.
    client = adapter._client  # type: ignore[attr-defined]
    end_time = None
    for _ in range(20):
        time.sleep(0.25)
        try:
            run = client.read_run(run_id)
        except LangSmithNotFoundError:
            # Backend can briefly return 404 right after create/update.
            continue
        end_time = getattr(run, "end_time", None)
        if end_time is not None:
            break

    assert end_time is not None, "LangSmith run end_time was not persisted; run may remain Pending."
