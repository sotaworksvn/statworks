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
# Presign (F-05 — infrastructure)
# ---------------------------------------------------------------------------

class PresignRequest(BaseModel):
    file_name: str


class PresignResponse(BaseModel):
    upload_url: str
    r2_key: str


# ---------------------------------------------------------------------------
# Dataset listing (F-05 — infrastructure)
# ---------------------------------------------------------------------------

class DatasetItem(BaseModel):
    id: str
    file_name: str
    r2_key: str
    created_at: str


class DatasetListResponse(BaseModel):
    datasets: list[DatasetItem]


# ---------------------------------------------------------------------------
# User sync (F-05 — Clerk ↔ Supabase)
# ---------------------------------------------------------------------------

class SyncUserRequest(BaseModel):
    clerk_user_id: str
    email: str | None = None
    name: str | None = None


class SyncUserResponse(BaseModel):
    id: str | None
    clerk_user_id: str
    synced: bool


# ---------------------------------------------------------------------------
# Internal models used across modules
# ---------------------------------------------------------------------------

class CleanedIntent(BaseModel):
    intent: str
    target: str
    features: list[str]
