from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

TraceBackend = Literal["none", "langsmith", "langfuse", "both"]


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    tracing_backend: TraceBackend
    langsmith_api_key: str | None
    langsmith_project: str | None
    langsmith_endpoint: str | None
    langfuse_public_key: str | None
    langfuse_secret_key: str | None
    langfuse_host: str | None
    log_level: str
    debug_internal: bool
    mt5_shared_secret: str
    mt5_bridge_mode: str
    enable_deepseek: bool
    model_market_reader: str
    model_tech_analysis: str
    model_risk_guard: str
    model_final_decider: str
    model_explainer: str
    ollama_url: str
    lmstudio_url: str | None
    gate_min_range: float
    gate_min_body: float
    gate_max_spread: float
    gate_max_ohlc_delta: float
    decision_cache_size: int
    enable_gating: bool


def _read_env() -> None:
    env_path = Path(__file__).resolve().parent.parent.parent / "Session6" / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def load_config() -> AppConfig:
    _read_env()
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8100"))
    tracing_backend: TraceBackend = os.getenv("TRACING_BACKEND", "both").lower()  # type: ignore[assignment]
    if tracing_backend not in {"none", "langsmith", "langfuse", "both"}:
        tracing_backend = "none"

    langsmith_api_key = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
    langsmith_project = os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT")
    langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT") or os.getenv("LANGCHAIN_ENDPOINT")

    return AppConfig(
        host=host,
        port=port,
        tracing_backend=tracing_backend,
        langsmith_api_key=langsmith_api_key,
        langsmith_project=langsmith_project,
        langsmith_endpoint=langsmith_endpoint,
        langfuse_public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
        langfuse_secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
        langfuse_host=os.getenv("LANGFUSE_HOST"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        debug_internal=os.getenv("DEBUG_INTERNAL", "0") in {"1", "true", "TRUE", "on"},
        mt5_shared_secret=os.getenv("MT5_SHARED_SECRET", "change_me"),
        mt5_bridge_mode=os.getenv("MT5_BRIDGE_MODE", "push"),
        enable_deepseek=os.getenv("ENABLE_DEEPSEEK_EXPERIMENT", "0") in {"1", "true", "TRUE"},
        model_market_reader=os.getenv("MODEL_MARKET_READER", "qwen2.5:7b"),
        model_tech_analysis=os.getenv("MODEL_TECH_ANALYSIS", "qwen3:8b"),
        model_risk_guard=os.getenv("MODEL_RISK_GUARD", "llama3.1:8b"),
        model_final_decider=os.getenv("MODEL_FINAL_DECIDER", "ministral-3:8b"),
        model_explainer=os.getenv("MODEL_EXPLAINER", "qwen3:8b"),
        ollama_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        lmstudio_url=os.getenv("LMSTUDIO_BASE_URL"),
        gate_min_range=float(os.getenv("GATE_MIN_RANGE", "0.4")),
        gate_min_body=float(os.getenv("GATE_MIN_BODY", "0.1")),
        gate_max_spread=float(os.getenv("GATE_MAX_SPREAD", "0.35")),
        gate_max_ohlc_delta=float(os.getenv("GATE_MAX_OHLC_DELTA", "5")),
        decision_cache_size=int(os.getenv("DECISION_CACHE_LIMIT", "64")),
        enable_gating=os.getenv("ENABLE_GATING", "1") in {"1", "true", "TRUE", "on"},
    )
