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
    method: str | None = None  # If set, bypass LLM and dispatch directly to this engine


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
    model_type: Literal["regression", "pls", "scholarship_pls"] | None
    decision_trace: DecisionTrace
    result_type: str = "regression"  # regression|scholarship_prediction|descriptive|...
    table_data: dict | None = None
    not_supported: bool = False
    suggestion: str | None = None
    # Scholarship-specific fields
    school_matches: list["SchoolMatch"] | None = None
    student_profile: dict | None = None


class StudentProfileResponse(AnalyzeResponse):
    """Extended response for the student_profile_analysis pipeline.

    Adds the 6 sections required for the full student analysis output.
    """
    # Section 1 & 3: SPSS-equivalent capability analysis
    capability_analysis: dict | None = None        # {gpa_trend, subject_stats, strength_breakdown, key_insights, ...}
    # Section 2 & 4: Web-searched scholarship opportunities
    scholarship_opportunities: list[dict] | None = None  # [{school_name, amount, deadline, match_score, ...}]
    # Section 5: Personalized roadmap
    roadmap: list[dict] | None = None             # [{month, phase, milestones, priority, notes}]
    # Section 6: Simulate bar config
    simulate_criteria: list[dict] | None = None   # [{key, label, type, min, max, step, current, options}]
    # Student profile full details
    student_profile_full: dict | None = None      # parsed StudentProfile dict
    student_tier: str | None = None               # "Top 1%" | "Top 5%" | ...



# ---------------------------------------------------------------------------
# Scholarship (EdTech Track)
# ---------------------------------------------------------------------------

class SchoolMatch(BaseModel):
    school_name: str
    country: str
    match_score: int  # 0-100
    match_level: Literal["dream", "target", "safety"]
    strengths: list[str]
    weaknesses: list[str]


class ScholarshipSimulateRequest(BaseModel):
    file_id: str
    school_name: str
    improvements: dict  # e.g. {"sat_score": 1500, "ielts_score": 7.5}


class ScholarshipSimulateResponse(BaseModel):
    type: str
    school_name: str
    current_score: int
    new_score: int
    delta: int
    level_change: str | None

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
# Dataset listing (F-05/F-08 — infrastructure + upload history)
# ---------------------------------------------------------------------------

class DatasetItem(BaseModel):
    id: str
    file_name: str
    r2_key: str
    created_at: str
    content_hash: str | None = None
    file_type: str | None = None


class DatasetListResponse(BaseModel):
    datasets: list[DatasetItem]


# ---------------------------------------------------------------------------
# Dataset content (F-06 — Data Viewer)
# ---------------------------------------------------------------------------

class DatasetContentResponse(BaseModel):
    """Response for GET /datasets/{id}/content — returns parsed data."""
    file_id: str
    file_name: str | None
    file_type: str | None
    columns: list[ColumnMeta]
    rows: list[dict]
    row_count: int
    context_text: str | None = None



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
# Conversations (F-09 — Chat History)
# ---------------------------------------------------------------------------

class ConversationItem(BaseModel):
    id: str
    title: str
    file_names: list[str] = []
    message_count: int = 0
    created_at: str
    updated_at: str


class ConversationListResponse(BaseModel):
    conversations: list[ConversationItem]


class CreateConversationRequest(BaseModel):
    title: str
    dataset_ids: list[str] = []


class MessageItem(BaseModel):
    id: str
    role: str  # "user" | "assistant"
    content: dict  # { type: "text", text: "..." } or { type: "insight", data: {...} }
    created_at: str


class MessageListResponse(BaseModel):
    conversation_id: str
    messages: list[MessageItem]


class CreateMessageRequest(BaseModel):
    role: str  # "user" | "assistant"
    content: dict  # { type: "text", text: "..." } or { type: "insight", data: {...} }


# ---------------------------------------------------------------------------
# Internal models used across modules
# ---------------------------------------------------------------------------

class CleanedIntent(BaseModel):
    intent: str
    target: str
    features: list[str]
    group_by: str | None = None
    not_supported_reason: str | None = None
    edits: list[dict] = []
