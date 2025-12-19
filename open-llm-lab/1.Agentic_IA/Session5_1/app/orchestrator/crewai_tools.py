from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.orchestrator.crewai_compat import patch_signals_for_windows
from app.orchestrator.tools_web import WebTools


class WebSearchArgs(BaseModel):
    query: str = Field(min_length=1)


class WebFetchArgs(BaseModel):
    url: str = Field(min_length=1)


def build_crewai_tools(*, web: WebTools, tracer=None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Create CrewAI BaseTool instances for web_search/web_fetch.

    `tracer` is an optional TraceSession-like object (span(name, inputs) -> context manager).
    """

    # CrewAI 1.7.0 imports Unix-only signals (e.g., SIGHUP) that don't exist on Windows.
    # Patch them before importing any CrewAI modules.
    patch_signals_for_windows()

    from crewai.tools.base_tool import BaseTool  # local import

    class WebSearchTool(BaseTool):
        def __init__(self) -> None:
            super().__init__(name="web_search", description="Search the web for relevant URLs.", args_schema=WebSearchArgs)

        def _run(self, query: str) -> Any:  # type: ignore[override]
            if tracer is None:
                results = web.web_search(query)
                return [{"url": r.url, "title": r.title} for r in results]
            with tracer.span("web_search", {"query": query}) as span:  # type: ignore[attr-defined]
                results = web.web_search(query)
                out = [{"url": r.url, "title": r.title} for r in results]
                span.end({"results": len(out), "top_urls": [r["url"] for r in out[:3]]})
                return out

    class WebFetchTool(BaseTool):
        def __init__(self) -> None:
            super().__init__(name="web_fetch", description="Fetch a URL and extract a short snippet.", args_schema=WebFetchArgs)

        def _run(self, url: str) -> Any:  # type: ignore[override]
            if tracer is None:
                return web.web_fetch(url)
            with tracer.span("web_fetch", {"url": url}) as span:  # type: ignore[attr-defined]
                out = web.web_fetch(url)
                span.end(
                    {
                        "blocked": bool(out.get("blocked")),
                        "snippet_chars": len(out.get("snippet") or ""),
                    }
                )
                return out

    return {"web_search": WebSearchTool(), "web_fetch": WebFetchTool()}
