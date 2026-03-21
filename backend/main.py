"""SOTA StatWorks — FastAPI application entry point."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.auth.context import get_current_user_id
from backend.config import CORS_ORIGINS
from backend.db import supabase as supa
from backend.models import (
    ColumnMeta,
    ConversationItem,
    ConversationListResponse,
    CreateConversationRequest,
    CreateMessageRequest,
    DatasetContentResponse,
    DatasetContentUpdateRequest,
    DatasetItem,
    DatasetListResponse,
    MessageItem,
    MessageListResponse,
    SyncUserRequest,
    SyncUserResponse,
)
from backend.upload import router as upload_router
from backend.analyze import router as analyze_router
from backend.simulate import router as simulate_router
from backend.store import get_entry, get_or_restore_entry, set_entry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SOTA StatWorks",
    description="AI-powered statistical decision engine",
    version="0.3.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check — used to pre-warm Render and for uptime monitors."""
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# User sync (F-05 — Clerk ↔ Supabase)
# ---------------------------------------------------------------------------

@app.post("/api/auth/sync-user", response_model=SyncUserResponse)
async def sync_user(body: SyncUserRequest) -> SyncUserResponse:
    """Upsert a Clerk user into Supabase.

    Called by the frontend on every login to ensure the user record
    exists in the ``users`` table before any uploads or analyses.
    Idempotent: safe to call repeatedly.
    """
    if not supa.is_available():
        return SyncUserResponse(
            id=None,
            clerk_user_id=body.clerk_user_id,
            synced=False,
        )

    db_id = supa.upsert_user(
        clerk_user_id=body.clerk_user_id,
        email=body.email,
        name=body.name,
    )

    return SyncUserResponse(
        id=db_id,
        clerk_user_id=body.clerk_user_id,
        synced=db_id is not None,
    )

# ---------------------------------------------------------------------------
# Datasets listing (F-05/F-08 — infrastructure + upload history)
# ---------------------------------------------------------------------------

datasets_router = APIRouter()


@datasets_router.get("/data", response_model=DatasetListResponse)
async def list_datasets(request: Request) -> DatasetListResponse:
    """List all datasets belonging to the authenticated user.

    Requires ``x-clerk-user-id`` header.  Returns an empty list if
    Supabase is not configured or user has no datasets.
    """
    clerk_user_id = get_current_user_id(request)
    if not clerk_user_id:
        raise HTTPException(
            status_code=401,
            detail="x-clerk-user-id header is required.",
        )

    if not supa.is_available():
        return DatasetListResponse(datasets=[])

    raw = supa.get_user_datasets(clerk_user_id)
    datasets = [
        DatasetItem(
            id=d["id"],
            file_name=d["file_name"],
            r2_key=d["r2_key"],
            created_at=d["created_at"],
            content_hash=d.get("content_hash"),
            file_type=d.get("file_type"),
        )
        for d in raw
    ]
    return DatasetListResponse(datasets=datasets)


# ---------------------------------------------------------------------------
# Dataset content (F-06 — Data Viewer)
# ---------------------------------------------------------------------------

@datasets_router.get("/data/{dataset_id}/content", response_model=DatasetContentResponse)
async def get_dataset_content(
    dataset_id: str,
    limit: int = 500,
    offset: int = 0,
) -> DatasetContentResponse:
    """Retrieve the parsed content of a dataset for the Data Viewer.

    Returns a paginated slice of the DataFrame as a list of row dicts
    plus column metadata.  Default: first 500 rows (fast render).
    Max: 5000 rows per request.
    """
    limit = min(max(1, limit), 5000)
    offset = max(0, offset)

    entry = await get_or_restore_entry(dataset_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. It may have been evicted from cache and could not be restored from R2.",
        )

    columns = [
        ColumnMeta(
            name=c["name"],
            dtype=c["dtype"],
            is_numeric=c["is_numeric"],
        )
        for c in entry.columns
    ]

    # Slice the DataFrame for pagination — avoids serialising entire dataset
    df_slice = entry.dataframe.iloc[offset : offset + limit]

    # Convert slice to list of dicts, replacing NaN with None
    rows = df_slice.where(df_slice.notna(), None).to_dict(orient="records")

    return DatasetContentResponse(
        file_id=entry.file_id,
        file_name=entry.file_name,
        file_type=entry.file_type,
        columns=columns,
        rows=rows,
        row_count=entry.row_count,  # total rows, not sliced
        context_text=entry.context_text,
    )


@datasets_router.put("/data/{dataset_id}/content")
async def update_dataset_content(
    dataset_id: str,
    body: DatasetContentUpdateRequest,
) -> dict[str, str]:
    """Update a single cell value in the in-memory dataset.

    Used by the Data Viewer for inline editing.
    Changes are ephemeral (not persisted to R2 in v1).
    """
    entry = await get_entry(dataset_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="Dataset not found. It may have been evicted from cache.",
        )

    df = entry.dataframe
    if body.column_name not in df.columns:
        raise HTTPException(
            status_code=422,
            detail=f"Column '{body.column_name}' not found. Available: {list(df.columns)}",
        )

    if body.row_index < 0 or body.row_index >= len(df):
        raise HTTPException(
            status_code=422,
            detail=f"Row index {body.row_index} out of range [0, {len(df) - 1}].",
        )

    # Update the cell value
    df.at[body.row_index, body.column_name] = body.new_value  # type: ignore[assignment]
    await set_entry(entry)

    return {"status": "ok", "message": f"Updated [{body.row_index}, {body.column_name}]"}


# ---------------------------------------------------------------------------
# Conversations (F-09 — Chat History)
# ---------------------------------------------------------------------------

conversations_router = APIRouter()


@conversations_router.get("/conversations", response_model=ConversationListResponse)
async def list_conversations(request: Request) -> ConversationListResponse:
    """List all conversations belonging to the authenticated user.

    Returns newest-first, up to 50 conversations.
    Each item includes title, linked file names, and message count.
    """
    clerk_user_id = get_current_user_id(request)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="x-clerk-user-id header is required.")

    if not supa.is_available():
        return ConversationListResponse(conversations=[])

    raw = supa.get_user_conversations(clerk_user_id)
    conversations = [
        ConversationItem(
            id=c["id"],
            title=c["title"],
            file_names=c.get("file_names", []),
            message_count=c.get("message_count", 0),
            created_at=c["created_at"],
            updated_at=c["updated_at"],
        )
        for c in raw
    ]
    return ConversationListResponse(conversations=conversations)


@conversations_router.post("/conversations")
async def create_conversation(
    request: Request,
    body: CreateConversationRequest,
) -> dict:
    """Create a new conversation, optionally linking datasets.

    Auto-called when user uploads files. Title is auto-generated
    from the first query or uploaded file name.
    """
    clerk_user_id = get_current_user_id(request)
    if not clerk_user_id:
        raise HTTPException(status_code=401, detail="x-clerk-user-id header is required.")

    if not supa.is_available():
        # Return a fake conversation for in-memory-only mode
        import uuid as _uuid
        return {
            "id": str(_uuid.uuid4()),
            "title": body.title,
            "created_at": "in-memory",
            "updated_at": "in-memory",
        }

    conv = supa.create_conversation(
        clerk_user_id=clerk_user_id,
        title=body.title,
        dataset_ids=body.dataset_ids or None,
    )
    if conv is None:
        raise HTTPException(status_code=500, detail="Failed to create conversation.")

    return conv


@conversations_router.get("/conversations/{conversation_id}/messages", response_model=MessageListResponse)
async def get_messages(conversation_id: str) -> MessageListResponse:
    """Fetch all messages for a conversation, oldest-first."""
    if not supa.is_available():
        return MessageListResponse(conversation_id=conversation_id, messages=[])

    raw = supa.get_conversation_messages(conversation_id)
    messages = [
        MessageItem(
            id=m["id"],
            role=m["role"],
            content=m["content"],
            created_at=m["created_at"],
        )
        for m in raw
    ]
    return MessageListResponse(conversation_id=conversation_id, messages=messages)


@conversations_router.post("/conversations/{conversation_id}/messages")
async def create_message(
    conversation_id: str,
    body: CreateMessageRequest,
) -> dict:
    """Save a message (user query or assistant response) to a conversation.

    This is fire-and-forget from the frontend's perspective — it should
    not block the insight delivery pipeline.
    """
    if not supa.is_available():
        return {"status": "ok", "message": "Supabase not available — message not persisted."}

    msg_id = supa.create_message(
        conversation_id=conversation_id,
        role=body.role,
        content=body.content,
    )
    if msg_id is None:
        raise HTTPException(status_code=500, detail="Failed to save message.")

    return {"status": "ok", "id": msg_id}


# ---------------------------------------------------------------------------
# History — Autosave endpoints
# ---------------------------------------------------------------------------

from pydantic import BaseModel as _HBase
from backend.history_store import (
    save_entry as _hs_save,
    list_entries as _hs_list,
    get_entry as _hs_get,
    get_all_for_export as _hs_export,
    SESSION_START as _SESSION_START,
)


class _HistorySaveRequest(_HBase):
    category: str  # "chat" | "data" | "dashboard"
    title: str
    snapshot: dict


@app.get("/api/history")
async def list_history(
    request: Request,
    category: str | None = None,
    from_dt: str | None = None,
    to_dt: str | None = None,
):
    """List history entries with optional category and date filters."""
    user_id = get_current_user_id(request) or "anonymous"
    entries = _hs_list(user_id, category=category, from_dt=from_dt, to_dt=to_dt)
    return {"entries": entries}


@app.post("/api/history")
async def save_history(body: _HistorySaveRequest, request: Request):
    """Save a history snapshot (autosave from frontend)."""
    user_id = get_current_user_id(request) or "anonymous"
    if body.category not in ("chat", "data", "dashboard"):
        raise HTTPException(status_code=400, detail="category must be chat|data|dashboard")
    entry = _hs_save(
        user_id=user_id,
        category=body.category,
        title=body.title,
        snapshot=body.snapshot,
    )
    return {"status": "ok", "id": entry.id, "created_at": entry.created_at}


# ---------------------------------------------------------------------------
# Cell Editing  (PATCH /datasets/{file_id}/cells)
# ---------------------------------------------------------------------------


class CellEdit(_HBase):
    """A single cell edit."""
    row: int | None = None           # direct row index (0-based)
    column: str                       # target column
    value: Any                       # new value
    filter_column: str | None = None  # for AI: match rows where filter_column == filter_value
    filter_value: str | None = None


class CellEditBatch(_HBase):
    edits: list[CellEdit]


@app.patch("/api/data/{file_id}/cells")
async def patch_cells(file_id: str, body: CellEditBatch):
    """Apply batch cell edits to the in-memory DataFrame."""
    from backend.store import get_entry, set_entry

    entry = await get_entry(file_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    df = entry.dataframe
    applied = 0

    for edit in body.edits:
        if edit.column not in df.columns:
            continue

        if edit.filter_column and edit.filter_value is not None:
            # AI-driven: find rows matching filter
            if edit.filter_column not in df.columns:
                continue
            mask = df[edit.filter_column].astype(str) == str(edit.filter_value)
            if mask.any():
                df.loc[mask, edit.column] = edit.value
                applied += mask.sum()
        elif edit.row is not None and 0 <= edit.row < len(df):
            # Direct row index edit
            df.iloc[edit.row, df.columns.get_loc(edit.column)] = edit.value
            applied += 1

    entry.dataframe = df
    entry.row_count = len(df)
    await set_entry(entry)

    return {"status": "ok", "applied": int(applied), "row_count": len(df)}


# ---------------------------------------------------------------------------
# PDF Export — MUST be registered BEFORE /api/history/{entry_id}
# to avoid FastAPI route conflict (Bug #1 fix)
# ---------------------------------------------------------------------------


@app.get("/api/history/export-pdf")
async def export_pdf(
    request: Request,
    from_dt: str | None = None,
    to_dt: str | None = None,
    _clerk_user_id: str | None = None,
):
    """Generate an AI-analyzed PDF report of the user's work session.

    1. Collect all history entries within time range
    2. Send to LLM for analysis/organization
    3. Generate PDF with ReportLab (Arial font)
    4. Return as binary download
    """
    import io
    import json
    from datetime import datetime, timezone
    from fastapi.responses import StreamingResponse

    user_id = get_current_user_id(request) or _clerk_user_id or "anonymous"
    logger.info("export_pdf: resolved user_id=%s (header=%s, qp=%s)",
                user_id, get_current_user_id(request), _clerk_user_id)
    # Default: only current session (from server start to now)
    effective_from = from_dt or _SESSION_START
    entries = _hs_export(user_id, from_dt=effective_from, to_dt=to_dt)

    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No history entries found for user '{user_id}' in the selected time range. "
                   "Make sure you have performed some analyses or edits before exporting.",
        )

    # --- Step 1: Prepare data for LLM ---
    entry_summaries = []
    for e in entries:
        entry_summaries.append({
            "time": e.created_at,
            "type": e.category,
            "title": e.title,
            "data": json.dumps(e.snapshot, ensure_ascii=False, default=str)[:500],
        })

    # --- Step 2: LLM analysis (async, with key rotation) ---
    ai_report = ""
    try:
        from backend.llm.client import call_llm_with_retry, LLMFailureError
        from backend.llm.prompts import SYSTEM_PROMPT_REPORT

        llm_result = await call_llm_with_retry(
            model="gpt-5.4-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_REPORT},
                {"role": "user", "content": json.dumps(entry_summaries, ensure_ascii=False, default=str)},
            ],
            response_format={"type": "json_object"},
        )
        ai_report = llm_result.get("report", str(llm_result))
    except (LLMFailureError, Exception) as exc:
        logger.warning("LLM report generation failed: %s", exc)
        ai_report = "AI analysis unavailable. Raw session data is included below."

    # --- Step 3: Generate PDF with ReportLab ---
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm,
                                topMargin=2 * cm, bottomMargin=2 * cm)

        styles = getSampleStyleSheet()
        # Use Arial via Helvetica (built-in, visually identical)
        title_style = ParagraphStyle("ReportTitle", parent=styles["Title"],
                                     fontName="Helvetica-Bold", fontSize=20,
                                     textColor=HexColor("#2D3561"), spaceAfter=12)
        heading_style = ParagraphStyle("ReportH2", parent=styles["Heading2"],
                                       fontName="Helvetica-Bold", fontSize=14,
                                       textColor=HexColor("#2D3561"), spaceAfter=8)
        body_style = ParagraphStyle("ReportBody", parent=styles["Normal"],
                                     fontName="Helvetica", fontSize=10,
                                     leading=14, spaceAfter=6)
        meta_style = ParagraphStyle("ReportMeta", parent=styles["Normal"],
                                     fontName="Helvetica", fontSize=9,
                                     textColor=HexColor("#6b7280"))

        # ── Markdown → ReportLab converter ──────────────────────────────────
        import re

        h3_style = ParagraphStyle("ReportH3", parent=styles["Heading3"],
                                   fontName="Helvetica-Bold", fontSize=12,
                                   textColor=HexColor("#2D3561"), spaceAfter=6,
                                   spaceBefore=10)
        bullet_style = ParagraphStyle("ReportBullet", parent=body_style,
                                       bulletIndent=10, leftIndent=24,
                                       spaceAfter=3)
        numbered_style = ParagraphStyle("ReportNumbered", parent=body_style,
                                         bulletIndent=10, leftIndent=24,
                                         spaceAfter=3)
        hr_style = ParagraphStyle("ReportHR", parent=styles["Normal"],
                                    fontSize=2, spaceAfter=8, spaceBefore=8)

        def _md_inline(text: str) -> str:
            """Convert inline markdown to ReportLab XML: bold, italic, code."""
            # Escape XML first
            text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            # Bold: **text** or __text__
            text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
            text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
            # Italic: *text* or _text_ (but not inside bold markers)
            text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
            text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'<i>\1</i>', text)
            # Inline code: `code`
            text = re.sub(r'`([^`]+)`', r'<font face="Courier" size="9">\1</font>', text)
            return text

        def _md_to_elements(md_text: str) -> list:
            """Convert markdown text to a list of ReportLab flowable elements."""
            result = []
            for raw_line in md_text.split("\n"):
                line = raw_line.strip()
                if not line:
                    continue

                # --- Horizontal rule ---
                if re.match(r'^-{3,}$|^\*{3,}$|^_{3,}$', line):
                    from reportlab.platypus import HRFlowable
                    result.append(HRFlowable(
                        width="100%", thickness=1,
                        color=HexColor("#D1D5DB"), spaceAfter=8, spaceBefore=8,
                    ))
                    continue

                # --- Headings ---
                heading_match = re.match(r'^(#{1,3})\s+(.+)', line)
                if heading_match:
                    level = len(heading_match.group(1))
                    text = _md_inline(heading_match.group(2))
                    if level == 1:
                        result.append(Paragraph(text, heading_style))
                    elif level == 2:
                        result.append(Paragraph(text, heading_style))
                    else:
                        result.append(Paragraph(text, h3_style))
                    continue

                # --- Bullet list: - item or * item ---
                bullet_match = re.match(r'^[-*]\s+(.+)', line)
                if bullet_match:
                    text = _md_inline(bullet_match.group(1))
                    result.append(Paragraph(f"• {text}", bullet_style))
                    continue

                # --- Numbered list: 1. item ---
                numbered_match = re.match(r'^(\d+)\.\s+(.+)', line)
                if numbered_match:
                    num = numbered_match.group(1)
                    text = _md_inline(numbered_match.group(2))
                    result.append(Paragraph(f"{num}. {text}", numbered_style))
                    continue

                # --- Regular paragraph ---
                text = _md_inline(line)
                result.append(Paragraph(text, body_style))

            return result

        elements = []

        # Title
        elements.append(Paragraph("SOTA StatWorks — Session Report", title_style))
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        elements.append(Paragraph(f"Generated: {now_str} | Entries: {len(entries)}", meta_style))
        elements.append(Spacer(1, 0.5 * cm))

        # AI Report
        elements.append(Paragraph("AI Analysis", heading_style))
        elements.extend(_md_to_elements(ai_report))
        elements.append(Spacer(1, 0.5 * cm))

        # Session Timeline
        elements.append(Paragraph("Session Timeline", heading_style))
        table_data = [["Time", "Type", "Title"]]
        for e in entries:
            ts = e.created_at[:19].replace("T", " ")
            table_data.append([ts, e.category.upper(), e.title[:50]])

        t = Table(table_data, colWidths=[4 * cm, 3 * cm, 9 * cm])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#2D3561")),
            ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
            ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#e5e7eb")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#ffffff"), HexColor("#f9fafb")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)

        doc.build(elements)
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=sota_statworks_report.pdf"},
        )
    except ImportError:
        # reportlab not installed — return plain text fallback
        return {"status": "error", "detail": "reportlab not installed. Run: pip install reportlab"}


# ---------------------------------------------------------------------------
# History entry by ID — MUST be AFTER /api/history/export-pdf (Bug #1 fix)
# ---------------------------------------------------------------------------

@app.get("/api/history/{entry_id}")
async def get_history_entry(entry_id: str):
    """Get a single history entry by ID (includes full snapshot)."""
    entry = _hs_get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    return {
        "id": entry.id,
        "category": entry.category,
        "title": entry.title,
        "snapshot": entry.snapshot,
        "created_at": entry.created_at,
    }


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(upload_router, prefix="/api")
app.include_router(analyze_router, prefix="/api/chat")
app.include_router(simulate_router, prefix="/api/monitor")
app.include_router(datasets_router, prefix="/api")
app.include_router(conversations_router, prefix="/api/chat")

