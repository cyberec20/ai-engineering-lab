from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


def test_smoke() -> None:
    os.environ["TRACE_PROVIDER"] = "none"
    os.environ["WEB_PROVIDER"] = "stub"
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.main import create_app

    app = create_app()
    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200

    payload = {"message": "¿Qué es internet?", "session_id": "test-session"}
    r = client.post("/chat", json=payload)
    assert r.status_code == 200
    data = r.json()

    assert data["session_id"]
    assert "status" in data
    assert "execution_summary" in data
    assert "sources" in data
