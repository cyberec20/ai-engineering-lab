from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


TraceProvider = Literal["none", "langsmith", "langfuse"]
WebProvider = Literal["live", "stub"]


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class LangSmithEnv:
    enabled: bool
    api_key: str | None
    endpoint: str
    project: str


@dataclass(frozen=True)
class LangfuseEnv:
    enabled: bool
    public_key: str | None
    secret_key: str | None
    base_url: str | None


@dataclass(frozen=True)
class AppConfig:
    host: str
    port: int
    trace_provider: TraceProvider
    web_provider: WebProvider

    ollama_base_url: str
    request_timeout_seconds: int

    max_turns: int
    max_queries: int
    max_fetches: int
    max_chars_per_page: int

    session_ttl_seconds: int
    session_max_entries: int

    model_research_lead: str
    model_web_researcher: str
    model_fact_checker: str
    model_synthesizer: str
    model_critic: str
    model_formatter: str


def load_langsmith_env() -> LangSmithEnv:
    import os

    provider = (os.getenv("TRACE_PROVIDER") or "none").strip().lower()
    enabled = provider == "langsmith"
    return LangSmithEnv(
        enabled=enabled,
        api_key=(os.getenv("LANGCHAIN_API_KEY") or "").strip() or None,
        endpoint=(os.getenv("LANGCHAIN_ENDPOINT") or "https://api.smith.langchain.com").strip(),
        project=(os.getenv("LANGCHAIN_PROJECT") or "Session5_1").strip(),
    )


def load_langfuse_env() -> LangfuseEnv:
    import os

    provider = (os.getenv("TRACE_PROVIDER") or "none").strip().lower()
    enabled = provider == "langfuse"
    return LangfuseEnv(
        enabled=enabled,
        public_key=(os.getenv("LANGFUSE_PUBLIC_KEY") or "").strip() or None,
        secret_key=(os.getenv("LANGFUSE_SECRET_KEY") or "").strip() or None,
        base_url=(os.getenv("LANGFUSE_BASE_URL") or "").strip() or None,
    )


def load_config() -> AppConfig:
    import os

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    trace_provider: TraceProvider = (os.getenv("TRACE_PROVIDER") or "none").strip().lower()  # type: ignore[assignment]
    if trace_provider not in {"none", "langsmith", "langfuse"}:
        trace_provider = "none"

    web_provider: WebProvider = (os.getenv("WEB_PROVIDER") or "live").strip().lower()  # type: ignore[assignment]
    if web_provider not in {"live", "stub"}:
        web_provider = "live"

    return AppConfig(
        host=(os.getenv("HOST") or "127.0.0.1").strip(),
        port=int(os.getenv("PORT") or "8100"),
        trace_provider=trace_provider,
        web_provider=web_provider,
        ollama_base_url=(os.getenv("OLLAMA_BASE_URL") or "http://127.0.0.1:11434").strip(),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS") or "25"),
        max_turns=int(os.getenv("MAX_TURNS") or "8"),
        max_queries=int(os.getenv("MAX_QUERIES") or "3"),
        max_fetches=int(os.getenv("MAX_FETCHES") or "3"),
        max_chars_per_page=int(os.getenv("MAX_CHARS_PER_PAGE") or "6000"),
        session_ttl_seconds=int(os.getenv("SESSION_TTL_SECONDS") or "1800"),
        session_max_entries=int(os.getenv("SESSION_MAX_ENTRIES") or "256"),
        model_research_lead=(os.getenv("MODEL_RESEARCH_LEAD") or "qwen3:8b").strip(),
        model_web_researcher=(os.getenv("MODEL_WEB_RESEARCHER") or "qwen2.5:7b").strip(),
        model_fact_checker=(os.getenv("MODEL_FACT_CHECKER") or "llama3.1:8b").strip(),
        model_synthesizer=(os.getenv("MODEL_SYNTHESIZER") or "ministral-3:8b").strip(),
        model_critic=(os.getenv("MODEL_CRITIC") or "llama3.1:8b").strip(),
        model_formatter=(os.getenv("MODEL_FORMATTER") or "qwen2.5:7b").strip(),
    )

