from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class PlannerOutput(BaseModel):
    plan: list[str] = Field(min_length=1)
    queries: list[str] = Field(min_length=1)

    @field_validator("plan", mode="before")
    @classmethod
    def _coerce_plan(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, dict):
            return [str(x).strip() for x in v.values() if str(x).strip()]
        if isinstance(v, str):
            lines = [x.strip(" -\t") for x in v.splitlines()]
            return [x for x in lines if x]
        return [str(v)]

    @field_validator("queries", mode="before")
    @classmethod
    def _coerce_queries(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, dict):
            return [str(x).strip() for x in v.values() if str(x).strip()]
        if isinstance(v, str):
            lines = [x.strip(" -\t") for x in v.splitlines()]
            return [x for x in lines if x]
        return [str(v)]


class Citation(BaseModel):
    url: str
    snippet_id: str


class KeyPoint(BaseModel):
    id: str
    claim: str
    citations: list[Citation] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)


class DraftAnswer(BaseModel):
    question: str
    key_points: list[KeyPoint] = Field(min_length=1)
    final_answer: str
    limitations: list[str] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)


class GuardVerdict(BaseModel):
    supported: bool
    missing_point_ids: list[str] = Field(default_factory=list)
    rationale: Optional[str] = None


class ExecutionStep(BaseModel):
    name: str
    status: Literal["OK", "WARN", "ERROR"]
    started_at: str
    ended_at: str | None = None
    details: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    run_id: str
    trace_id: str
    answer: str | None = None
    execution_summary: list[ExecutionStep] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    status: Literal["SUCCESS", "NEEDS_HITL", "FAILED"]
    hitl_required: bool = False
    hitl_token: str | None = None
    hitl_notes: str | None = None
    langsmith_run_id: str | None = None
    langfuse_trace_id: str | None = None
