from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class QueryInterpretation(BaseModel):
    input_language: str = Field(..., min_length=2, max_length=8)
    normalized_query: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    entities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    preferred_sources: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AgentSpec:
    role: str
    objective: str
    allowed_tools: list[str]
    model_name: str
    success_criteria: str


class EvidenceItem(BaseModel):
    url: str
    title: str | None = None
    snippet: str = ""
    fetched_text: str | None = None


class ChatResult(BaseModel):
    session_id: str
    answer: str
    sources: list[str]
    agents_created: list[dict]
    models_used: list[str]
    execution_summary: list[dict]
    run_id: str | None = None
    trace_id: str | None = None
    status: Literal["SUCCESS", "INSUFFICIENT_EVIDENCE", "FAILED", "NEEDS_HITL"] = "SUCCESS"
    hitl_required: bool = False
    hitl_token: str | None = None
    hitl_notes: str | None = None


class ApproveResult(BaseModel):
    session_id: str
    answer: str
    sources: list[str]
    execution_summary: list[dict]
    run_id: str | None = None
    trace_id: str | None = None
    status: Literal["SUCCESS", "INSUFFICIENT_EVIDENCE", "FAILED", "NEEDS_HITL"] = "SUCCESS"
    hitl_required: bool = False
    hitl_token: str | None = None
    hitl_notes: str | None = None

