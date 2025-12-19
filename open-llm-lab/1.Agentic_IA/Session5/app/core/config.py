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

    trace_provider: str  # none | langsmith | langfuse
    web_provider: str  # live | stub

    ollama_base_url: str
    request_timeout_seconds: int

    max_turns: int
    max_queries: int
    max_fetches: int
    max_chars_per_page: int

    session_ttl_seconds: int
    session_max_entries: int

    # Models (explicit mapping)
    model_research_lead: str
    model_web_researcher: str
    model_fact_checker: str
    model_synthesizer: str
    model_critic: str
    model_formatter: str

    enable_llm_query_interpreter: bool
    enable_llm_synthesizer: bool
    enable_llm_critic: bool


def load_config() -> AppConfig:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8100"))

    trace_provider = (os.getenv("TRACE_PROVIDER", "none") or "none").strip().lower()
    if trace_provider not in {"none", "langsmith", "langfuse"}:
        trace_provider = "none"

    web_provider = (os.getenv("WEB_PROVIDER", "live") or "live").strip().lower()
    if web_provider not in {"live", "stub"}:
        web_provider = "live"

    return AppConfig(
        host=host,
        port=port,
        trace_provider=trace_provider,
        web_provider=web_provider,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "25")),
        max_turns=int(os.getenv("MAX_TURNS", "8")),
        max_queries=int(os.getenv("MAX_QUERIES", "3")),
        max_fetches=int(os.getenv("MAX_FETCHES", "3")),
        max_chars_per_page=int(os.getenv("MAX_CHARS_PER_PAGE", "6000")),
        session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS", "1800")),
        session_max_entries=int(os.getenv("SESSION_MAX_ENTRIES", "256")),
        model_research_lead=os.getenv("MODEL_RESEARCH_LEAD", "qwen3:8b"),
        model_web_researcher=os.getenv("MODEL_WEB_RESEARCHER", "deepseek-r1:8b"),
        model_fact_checker=os.getenv("MODEL_FACT_CHECKER", "llama3.1:8b"),
        model_synthesizer=os.getenv("MODEL_SYNTHESIZER", "ministral-3:8b"),
        model_critic=os.getenv("MODEL_CRITIC", "llama3.1:8b"),
        model_formatter=os.getenv("MODEL_FORMATTER", "qwen2.5:7b"),
        enable_llm_query_interpreter=_truthy(os.getenv("ENABLE_LLM_QUERY_INTERPRETER", "true")),
        enable_llm_synthesizer=_truthy(os.getenv("ENABLE_LLM_SYNTHESIZER", "true")),
        enable_llm_critic=_truthy(os.getenv("ENABLE_LLM_CRITIC", "false")),
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

    if api_key and "PASTE" in api_key:
        api_key = None
    if project and "PASTE" in project:
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

