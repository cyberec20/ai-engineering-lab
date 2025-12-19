from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import AppConfig, load_config
from .logging_setup import setup_logging
from .mcp_server import create_mcp_server
from .mt5_bridge import MT5Bridge, MT5BridgeStub
from .orchestrator import evaluate
from .schemas import DeskEvaluateRequest, DeskEvaluateResponse, PushPayload


def create_app() -> FastAPI:
    config = load_config()
    setup_logging(config)

    bridge: MT5Bridge = MT5Bridge()
    if config.debug_internal:
        bridge = MT5BridgeStub()

    app = FastAPI(title="Session6 MCP Desk")
    app.state.config = config
    app.state.bridge = bridge

    static_dir = Path(__file__).resolve().parent.parent / "web"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    def get_config() -> AppConfig:
        return app.state.config

    def get_bridge() -> MT5Bridge:
        return app.state.bridge

    @app.post("/api/desk/evaluate", response_model=DeskEvaluateResponse)
    async def api_evaluate(payload: DeskEvaluateRequest, config: AppConfig = Depends(get_config), bridge: MT5Bridge = Depends(get_bridge)):
        return evaluate(config, bridge, payload)

    @app.get("/api/logs/recent")
    async def logs_recent() -> JSONResponse:
        log_path = Path(__file__).resolve().parent.parent / "logs" / "runtime.jsonl"
        if not log_path.exists():
            return JSONResponse([])
        lines = log_path.read_text(encoding="utf-8").splitlines()[-200:]
        return JSONResponse(lines)

    @app.post("/mt5/push")
    async def mt5_push(payload: PushPayload, request: Request, config: AppConfig = Depends(get_config), bridge: MT5Bridge = Depends(get_bridge)):
        token = request.headers.get("X-MT5-Token")
        if token != config.mt5_shared_secret:
            raise HTTPException(status_code=401, detail="invalid token")
        bridge.push(payload)
        return {"status": "ok"}

    mcp_server = create_mcp_server(app, config, bridge)
    app.state.mcp_server = mcp_server
    return app


app = create_app()
