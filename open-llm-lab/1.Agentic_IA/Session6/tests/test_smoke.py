from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from mcp import types

import server.app as app_module  # type: ignore

SESSION_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SESSION_ROOT))
def test_health_and_evaluate():
    os.environ["DEBUG_INTERNAL"] = "1"
    client = TestClient(app_module.create_app())

    res = client.get("/health")
    assert res.status_code == 200

    payload = {"symbol": "XAU/USD (broker: GOLD-T)", "timeframe": "M1"}
    res = client.post("/api/desk/evaluate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "decision" in data
    assert "meta" in data


@pytest.mark.anyio
async def test_mcp_tools_and_desk():
    os.environ["DEBUG_INTERNAL"] = "1"
    app = app_module.create_app()
    mcp_server = getattr(app.state, "mcp_server")

    tool_list = await mcp_server.list_tools()
    tool_names = {tool.name for tool in tool_list}
    assert {"market.get_latest", "market.get_ohlc", "desk.evaluate"} <= tool_names

    latest = await mcp_server.call_tool(
        "market.get_latest",
        {"symbol": "XAU/USD (broker: GOLD-T)", "timeframe": "M1"},
    )
    assert latest

    desk_result = await mcp_server.call_tool(
        "desk.evaluate",
        {"symbol": "XAU/USD (broker: GOLD-T)", "timeframe": "M1", "notes": "smoke"},
    )
    assert desk_result
