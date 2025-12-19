from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceItem(BaseModel):
    url: str
    title: str | None = None
    snippet: str = ""


class ChatResult(BaseModel):
    session_id: str
    answer: str
    sources: list[str]
    agents_created: list[dict] = Field(default_factory=list)
    models_used: list[str] = Field(default_factory=list)
    execution_summary: list[dict] = Field(default_factory=list)
    run_id: str | None = None
    trace_id: str | None = None
    status: str
    hitl_required: bool = False
    hitl_token: str | None = None
    hitl_notes: str | None = None


class ApproveResult(BaseModel):
    session_id: str
    answer: str
    sources: list[str]
    execution_summary: list[dict] = Field(default_factory=list)
    run_id: str | None = None
    trace_id: str | None = None
    status: str
    hitl_required: bool = False
    hitl_token: str | None = None
    hitl_notes: str | None = None


class InterpreterOutput(BaseModel):
    input_language: str = "en"
    normalized_query: str
    intent: str = "open_question"
    entities: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    constraints: dict = Field(default_factory=dict)
    preferred_sources: list[str] = Field(default_factory=list)


class PlanOutput(BaseModel):
    plan: list[str]
    queries: list[str]


class WebResearchOutput(BaseModel):
    evidence: list[EvidenceItem]


class Verdict(BaseModel):
    status: str
    missing: list[str] = Field(default_factory=list)
    notes: str = ""
    required_actions: list[str] = Field(default_factory=list)


class VerdictOutput(BaseModel):
    verdict: Verdict


class DraftKeyPoint(BaseModel):
    claim: str
    citations: list[dict] = Field(default_factory=list)


class Draft(BaseModel):
    final_answer: str
    key_points: list[DraftKeyPoint] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    followups: list[str] = Field(default_factory=list)


class DraftOutput(BaseModel):
    draft: Draft

