from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int

    ollama_base_url: str
    request_timeout_seconds: int
    max_iterations: int

    trace_provider: str  # none | langsmith | langfuse

    # Performance / behavior knobs
    graph_mode: str  # full | fast
    web_max_results: int
    web_max_queries: int
    web_fetches_per_query: int
    web_min_delay_seconds: float
    web_cache_ttl_seconds: int
    web_cache_max_entries: int
    enable_llm_planner: bool
    enable_llm_synthesizer: bool
    enable_llm_guard_rationale: bool
    enable_llm_reflector: bool
    translation_retries: int

    # Model mapping (explicit per system_prompt_4.md)
    model_planner: str
    model_researcher: str
    model_synthesizer: str
    model_guard: str
    model_reflector: str


def load_config() -> AppConfig:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8100"))

    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    request_timeout_seconds = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
    max_iterations = int(os.getenv("MAX_ITERATIONS", "2"))

    trace_provider = (os.getenv("TRACE_PROVIDER", "none") or "none").strip().lower()
    if trace_provider not in {"none", "langsmith", "langfuse"}:
        trace_provider = "none"

    graph_mode = (os.getenv("GRAPH_MODE", "fast") or "fast").strip().lower()
    if graph_mode not in {"full", "fast"}:
        graph_mode = "fast"

    return AppConfig(
        host=host,
        port=port,
        ollama_base_url=ollama_base_url,
        request_timeout_seconds=request_timeout_seconds,
        max_iterations=max_iterations,
        trace_provider=trace_provider,
        graph_mode=graph_mode,
        web_max_results=int(os.getenv("WEB_MAX_RESULTS", "4")),
        web_max_queries=int(os.getenv("WEB_MAX_QUERIES", "3")),
        web_fetches_per_query=int(os.getenv("WEB_FETCHES_PER_QUERY", "1")),
        web_min_delay_seconds=float(os.getenv("WEB_MIN_DELAY_SECONDS", "0.2")),
        web_cache_ttl_seconds=int(os.getenv("WEB_CACHE_TTL_SECONDS", "900")),
        web_cache_max_entries=int(os.getenv("WEB_CACHE_MAX_ENTRIES", "256")),
        enable_llm_planner=_truthy(os.getenv("ENABLE_LLM_PLANNER", "false")),
        enable_llm_synthesizer=_truthy(os.getenv("ENABLE_LLM_SYNTHESIZER", "true")),
        enable_llm_guard_rationale=_truthy(os.getenv("ENABLE_LLM_GUARD_RATIONALE", "false")),
        enable_llm_reflector=_truthy(os.getenv("ENABLE_LLM_REFLECTOR", "false")),
        translation_retries=int(os.getenv("TRANSLATION_RETRIES", "1")),
        model_planner=os.getenv("MODEL_PLANNER", "qwen3:8b"),
        model_researcher=os.getenv("MODEL_RESEARCHER", "deepseek-r1:8b"),
        model_synthesizer=os.getenv("MODEL_SYNTHESIZER", "ministral-3:8b"),
        model_guard=os.getenv("MODEL_GUARD", "llama3.1:8b"),
        model_reflector=os.getenv("MODEL_REFLECTOR", "deepseek-r1:8b"),
    )


@dataclass(frozen=True)
class LangSmithEnv:
    enabled: bool
    api_key: str | None
    endpoint: str | None
    project: str | None


def load_langsmith_env() -> LangSmithEnv:
    api_key = os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY")
    endpoint = os.getenv("LANGCHAIN_ENDPOINT") or os.getenv("LANGSMITH_ENDPOINT")
    project = os.getenv("LANGCHAIN_PROJECT") or os.getenv("LANGSMITH_PROJECT")
    enabled = (
        _truthy(os.getenv("LANGCHAIN_TRACING_V2"))
        or _truthy(os.getenv("LANGSMITH_TRACING"))
        or (os.getenv("TRACE_PROVIDER", "").strip().lower() == "langsmith")
    )

    if api_key and "PASTE_YOUR" in api_key:
        api_key = None
    if project and "PASTE_" in project:
        project = None

    enabled = enabled and bool(api_key)
    return LangSmithEnv(enabled=enabled, api_key=api_key, endpoint=endpoint, project=project)


@dataclass(frozen=True)
class LangfuseEnv:
    enabled: bool
    base_url: str | None
    public_key: str | None
    secret_key: str | None


def load_langfuse_env() -> LangfuseEnv:
    base_url = os.getenv("LANGFUSE_BASE_URL") or os.getenv("LANGFUSE_HOST")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if public_key and "PASTE" in public_key:
        public_key = None
    if secret_key and "PASTE" in secret_key:
        secret_key = None

    enabled = bool(public_key and secret_key and base_url)
    return LangfuseEnv(enabled=enabled, base_url=base_url, public_key=public_key, secret_key=secret_key)
