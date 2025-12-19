from __future__ import annotations

import time
from typing import Any

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate

from server.config import AppConfig


class LLMClient:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def invoke(self, model: str, prompt: str, variables: dict[str, Any]) -> tuple[str, int]:
        started = time.perf_counter()
        llm = ChatOllama(base_url=self._config.ollama_url, model=model, temperature=0.2)
        template = ChatPromptTemplate.from_template(prompt)
        result = template | llm
        output = result.invoke(variables)
        latency = int((time.perf_counter() - started) * 1000)
        return output.content if hasattr(output, "content") else str(output), latency
