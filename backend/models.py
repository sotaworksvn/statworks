"""Pydantic models shared across all endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Upload (F-01)
# ---------------------------------------------------------------------------

class ColumnMeta(BaseModel):
    name: str
    dtype: str
    is_numeric: bool


class UploadResponse(BaseModel):
    file_id: str
    columns: list[ColumnMeta]
    row_count: int
    context_extracted: bool


# ---------------------------------------------------------------------------
# Analyze (F-02)
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    file_id: str
    query: str


class DriverResult(BaseModel):
    name: str
    coef: float
    p_value: float
    significant: bool


class DecisionTrace(BaseModel):
    score_pls: float
    score_reg: float
    engine_selected: str | None
    reason: str


class AnalyzeResponse(BaseModel):
    summary: str
    drivers: list[DriverResult]
    r2: float | None
    recommendation: str
    model_type: Literal["regression", "pls"] | None
    decision_trace: DecisionTrace


# ---------------------------------------------------------------------------
# Simulate (F-03)
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    file_id: str
    variable: str
    delta: float


class ImpactResult(BaseModel):
    variable: str
    delta_pct: float


class SimulationResponse(BaseModel):
    variable: str
    delta: float
    impacts: list[ImpactResult]


# ---------------------------------------------------------------------------
# Internal models used across modules
# ---------------------------------------------------------------------------

class CleanedIntent(BaseModel):
    intent: str
    target: str
    features: list[str]
