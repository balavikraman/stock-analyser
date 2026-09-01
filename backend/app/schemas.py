from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ScoreComponent(BaseModel):
    score: float | None = None
    confidence: float = Field(ge=0, le=1)
    label: str
    explanation: str


class JournalCreate(BaseModel):
    symbol: str
    action: str
    price: float | None = None
    quantity: float | None = None
    thesis: str = ""
    thesis_breaker: str = ""
    snapshot_id: int | None = None


class AnalysisReport(BaseModel):
    symbol: str
    company_name: str
    sector: str | None = None
    industry: str | None = None
    as_of: datetime
    price: float | None = None
    currency: str = "INR"
    scores: dict[str, ScoreComponent]
    overall_score: float | None
    overall_confidence: float
    verdict: str
    action_summary: str
    metrics: dict[str, Any]
    annuals: list[dict[str, Any]]
    quarterlies: list[dict[str, Any]]
    technicals: dict[str, Any]
    price_history: list[dict[str, Any]]
    entry_plan: dict[str, Any]
    scenarios: dict[str, Any]
    news: list[dict[str, Any]]
    risks: list[str]
    catalysts: list[str]
    data_quality: dict[str, Any]
    disclaimers: list[str]
