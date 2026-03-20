"""Stub POST /analyze — heuristic-only, no LLM (Phase 1 · task 1.8).

Updated for Phase 1.5: async Supabase result persistence.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from backend.engines.pls import PLSFallbackError, compute_pls
from backend.engines.regression import RegressionResultData, compute_ols
from backend.db import supabase as supa
from backend.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    DecisionTrace,
    DriverResult,
)
from backend.router import score_model
from backend.store import get_entry, set_entry
from backend.validation import validate_parsed_intent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """Stub analyse endpoint — no LLM, uses heuristics + statistical engines."""

    try:
        # 1. Lookup file_id
        entry = await get_entry(body.file_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail="file_id not found. Please upload a dataset first.",
            )

        df = entry.dataframe

        # 2. Stub intent parsing (no LLM) — treat everything as driver_analysis
        stub_parsed: dict = {
            "intent": "driver_analysis",
            "target": None,
            "features": [],
        }

        # 3. Validation layer
        cleaned = validate_parsed_intent(stub_parsed, df)

        # 4. Intent gate (for future use — currently always driver_analysis)
        if cleaned.intent != "driver_analysis":
            return AnalyzeResponse(
                summary="This type of analysis is not yet supported.",
                drivers=[],
                r2=None,
                recommendation=(
                    "Ask what drives a target variable, e.g. "
                    "'What affects retention?'"
                ),
                model_type=None,
                decision_trace=DecisionTrace(
                    score_pls=0.0,
                    score_reg=0.0,
                    engine_selected=None,
                    reason="Intent not supported.",
                ),
            )

        # 5. Decision Router
        trace = score_model(df, cleaned.features, cleaned.target)

        # 6. Run statistical engine
        result: RegressionResultData | None = None

        if trace.engine_selected == "pls":
            try:
                pls_result = compute_pls(
                    df, cleaned.features, cleaned.target
                )
                result = RegressionResultData(
                    drivers=pls_result.drivers,
                    r2=pls_result.r2,
                    model_type="pls",
                )
            except PLSFallbackError as pls_err:
                logger.warning("PLS failed, falling back to OLS: %s", pls_err)
                trace = DecisionTrace(
                    score_pls=trace.score_pls,
                    score_reg=trace.score_reg,
                    engine_selected="regression",
                    reason=(
                        trace.reason
                        + f" PLS fell back to regression: {pls_err}"
                    ),
                )

        if result is None:
            # Run OLS (either as primary or as PLS fallback)
            try:
                ols_result = compute_ols(
                    df, cleaned.features, cleaned.target
                )
                result = ols_result
            except Exception as ols_err:
                logger.error("OLS also failed: %s", ols_err)
                # Layer 3 fallback — return minimal valid response
                return AnalyzeResponse(
                    summary="Insufficient data for analysis.",
                    drivers=[],
                    r2=None,
                    recommendation=(
                        "Please check your dataset for missing or constant values."
                    ),
                    model_type=None,
                    decision_trace=DecisionTrace(
                        score_pls=trace.score_pls,
                        score_reg=trace.score_reg,
                        engine_selected=None,
                        reason="All engines failed. " + str(ols_err),
                    ),
                )

        # 7. Store coefficient cache for /simulate
        coefficient_cache: dict[str, list[tuple[str, float]]] = {}
        for d in result.drivers:
            coefficient_cache.setdefault(d.name, []).append(
                (cleaned.target, d.coef)
            )
        entry.coefficient_cache = coefficient_cache
        await set_entry(entry)

        # 8. Template-generated summary/recommendation (no LLM in Phase 1)
        top_driver = result.drivers[0] if result.drivers else None
        if top_driver:
            summary = (
                f"{top_driver.name} shows the strongest relationship with "
                f"{cleaned.target} (impact score {abs(top_driver.coef):.2f})."
            )
            recommendation = (
                f"Focus resources on improving {top_driver.name} to drive "
                f"better {cleaned.target} outcomes."
            )
        else:
            summary = "No strong drivers identified."
            recommendation = "Try a different question or check your dataset."

        # 9. Build response
        drivers_out = [
            DriverResult(
                name=d.name,
                coef=d.coef,
                p_value=d.p_value,
                significant=d.significant,
            )
            for d in result.drivers
        ]

        response = AnalyzeResponse(
            summary=summary,
            drivers=drivers_out,
            r2=result.r2,
            recommendation=recommendation,
            model_type=result.model_type,  # type: ignore[arg-type]
            decision_trace=trace,
        )

        # 10. Async Supabase persistence (fire-and-forget, non-blocking)
        if entry.user_id and supa.is_available():
            asyncio.create_task(
                _persist_analysis_result(entry.file_id, response.model_dump())
            )

        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Unexpected error in /analyze")
        raise HTTPException(
            status_code=500,
            detail="Unexpected error. Please try again.",
        ) from exc


async def _persist_analysis_result(file_id: str, result_dict: dict) -> None:
    """Persist analysis result to Supabase (non-blocking background task)."""
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, supa.create_analysis, file_id, result_dict,
        )
        logger.info("Analysis result persisted to Supabase for file_id=%s", file_id)
    except Exception as exc:
        logger.error("Supabase analysis persist failed: %s", exc)
