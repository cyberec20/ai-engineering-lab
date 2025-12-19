from __future__ import annotations

import os

from fastapi.testclient import TestClient


def test_smoke_health_and_chat() -> None:
    os.environ["TRACE_PROVIDER"] = "none"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["WEB_PROVIDER"] = "stub"

    from app.main import create_app  # imported after env set

    app = create_app()
    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"

    r = client.post("/chat", json={"message": "Isaac Newton", "session_id": "smoke"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in {"SUCCESS", "INSUFFICIENT_EVIDENCE", "FAILED", "NEEDS_HITL"}
    assert "execution_summary" in data
    assert "answer" in data
    assert "sources" in data

