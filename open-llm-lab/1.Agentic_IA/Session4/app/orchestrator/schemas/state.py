from __future__ import annotations

import operator
from typing import Literal, NotRequired, TypedDict
from typing_extensions import Annotated


class SearchResultDict(TypedDict):
    title: str
    url: str
    snippet: str


class SnippetDict(TypedDict):
    id: str
    url: str
    title: str | None
    snippet: str
    fetched_text: str | None


class ResearchState(TypedDict, total=False):
    user_message: str
    input_language: str
    plan: list[str]
    queries: list[str]
    web_results: list[SearchResultDict]
    snippets: dict[str, SnippetDict]
    sources: list[str]

    draft_answer: dict
    final_answer: str

    iteration_count: int
    status: Literal["SUCCESS", "NEEDS_HITL", "FAILED"]
    hitl_required: bool
    hitl_notes: str | None
    guard_executed: bool

    run_id: str
    trace_id: str
    timestamps: dict
    execution_summary: Annotated[list[dict], operator.add]

    langsmith_run_id: NotRequired[str | None]
    langfuse_trace_id: NotRequired[str | None]
