from __future__ import annotations

import os
from typing import List

from langchain_core.tracers import LangChainTracer

try:
    from langfuse.callback import CallbackHandler as LangfuseCallbackHandler
except Exception:  # pragma: no cover
    LangfuseCallbackHandler = None

from .config import AppConfig


def build_callbacks(config: AppConfig) -> List:
    callbacks: List = []
    backend = config.tracing_backend
    if backend in {"langsmith", "both"} and config.langsmith_api_key:
        os.environ.setdefault("LANGCHAIN_API_KEY", config.langsmith_api_key)
        os.environ.setdefault("LANGSMITH_API_KEY", config.langsmith_api_key)
        if config.langsmith_project:
            os.environ.setdefault("LANGCHAIN_PROJECT", config.langsmith_project)
            os.environ.setdefault("LANGSMITH_PROJECT", config.langsmith_project)
        if config.langsmith_endpoint:
            os.environ.setdefault("LANGCHAIN_ENDPOINT", config.langsmith_endpoint)
            os.environ.setdefault("LANGSMITH_ENDPOINT", config.langsmith_endpoint)
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
        os.environ.setdefault("LANGSMITH_TRACING", "false")
        tracer = LangChainTracer(project_name=config.langsmith_project or "Session6")
        callbacks.append(tracer)
    if backend in {"langfuse", "both"} and LangfuseCallbackHandler and config.langfuse_public_key and config.langfuse_secret_key:
        handler = LangfuseCallbackHandler(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
            host=config.langfuse_host,
        )
        callbacks.append(handler)
    return callbacks
