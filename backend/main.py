"""SOTA StatWorks — FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from backend.auth.context import get_current_user_id
from backend.config import CORS_ORIGIN
from backend.db import supabase as supa
from backend.models import DatasetItem, DatasetListResponse
from backend.upload import router as upload_router
from backend.analyze import router as analyze_router
from backend.simulate import router as simulate_router

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SOTA StatWorks",
    description="AI-powered statistical decision engine",
    version="0.2.0",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict[str, str]:
    """Health check — used to pre-warm Render and for uptime monitors."""
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Datasets listing (F-05 — infrastructure)
# ---------------------------------------------------------------------------

datasets_router = APIRouter()


@datasets_router.get("/datasets", response_model=DatasetListResponse)
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
        )
        for d in raw
    ]
    return DatasetListResponse(datasets=datasets)


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(upload_router)
app.include_router(analyze_router)
app.include_router(simulate_router)
app.include_router(datasets_router)

