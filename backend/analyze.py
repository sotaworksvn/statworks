"""POST /analyze — Full AI pipeline with 2-call LLM integration (Phase 2).

Pipeline:
  1. Lookup file_id
  2. LLM Call 1: intent parsing (gpt-5.4-mini)
  3. Validation Layer
  4. Intent gate
  5. Decision Router
  6. Statistical Engine (with PLS→OLS fallback)
  7. Store coefficient cache
  8. LLM Call 2: insight generation (gpt-5.4)
  9. Assemble and return AnalyzeResponse
  10. Async Supabase persistence

Rule references:
- Error Handling: 4-layer fallback chain  (04-rule.md)
- AI/LLM: ≤2 calls per request           (04-rule.md)
- Security: LLM output through Validation (04-rule.md)
- Performance: <2s enforce at handler     (04-rule.md)
"""

from __future__ import annotations

import asyncio
import logging
import time

from fastapi import APIRouter, HTTPException

from backend.engines.pls import PLSFallbackError, compute_pls
from backend.engines.regression import RegressionResultData, compute_ols
from backend.db import supabase as supa
from backend.llm.insight import generate_insight
from backend.llm.parser import parse_user_intent
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
    """Full AI-powered driver analysis endpoint."""

    try:
        t_start = time.perf_counter()

        # ---------------------------------------------------------------
        # Step 1: Lookup file_id → 404 if missing
        # ---------------------------------------------------------------
        entry = await get_entry(body.file_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail="file_id not found. Please upload a dataset first.",
            )

        df = entry.dataframe
        column_names = df.columns.tolist()

        # ---------------------------------------------------------------
        # Step 2: LLM Call 1 — intent parsing (gpt-5.4-mini)
        #         On failure → Layer 1 fallback (auto-select features)
        # ---------------------------------------------------------------
        parsed = await parse_user_intent(
            query=body.query,
            column_names=column_names,
            context_text=entry.context_text,
        )

        # ---------------------------------------------------------------
        # Step 3: Validation Layer
        #         The handler NEVER touches raw LLM output directly.
        # ---------------------------------------------------------------
        cleaned = validate_parsed_intent(parsed, df)

        # ---------------------------------------------------------------
        # Step 4: Intent gate
        # ---------------------------------------------------------------
        if cleaned.intent != "driver_analysis":
            return AnalyzeResponse(
                summary="This type of analysis is not yet supported.",
                drivers=[],
                r2=None,
                recommendation=(
                    f"Ask what drives {cleaned.target}, e.g. "
                    f"'What affects {cleaned.target}?'"
                ),
                model_type=None,
                decision_trace=DecisionTrace(
                    score_pls=0.0,
                    score_reg=0.0,
                    engine_selected=None,
                    reason="Intent not supported.",
                ),
            )

        # ---------------------------------------------------------------
        # Step 5: Decision Router
        # ---------------------------------------------------------------
        trace = score_model(df, cleaned.features, cleaned.target)

        # ---------------------------------------------------------------
        # Step 6: Run statistical engine
        #         Layer 2: PLS fails → OLS
        #         Layer 3: OLS fails → minimal valid response
        # ---------------------------------------------------------------
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
                # Layer 3: return minimal valid response
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

        # ---------------------------------------------------------------
        # Step 7: Store coefficient cache for /simulate
        # ---------------------------------------------------------------
        coefficient_cache: dict[str, list[tuple[str, float]]] = {}
        for d in result.drivers:
            coefficient_cache.setdefault(d.name, []).append(
                (cleaned.target, d.coef)
            )
        entry.coefficient_cache = coefficient_cache
        await set_entry(entry)

        # ---------------------------------------------------------------
        # Step 8: LLM Call 2 — insight generation (gpt-5.4)
        #         On failure → Layer 4 fallback (template strings)
        # ---------------------------------------------------------------
        drivers_dicts = [
            {
                "name": d.name,
                "coef": d.coef,
                "p_value": d.p_value,
                "significant": d.significant,
            }
            for d in result.drivers
        ]
        insight = await generate_insight(
            drivers=drivers_dicts,
            r2=result.r2,
            target=cleaned.target,
            model_type=result.model_type,
        )

        # ---------------------------------------------------------------
        # Step 9: Assemble and return full AnalyzeResponse
        # ---------------------------------------------------------------
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
            summary=insight.summary,
            drivers=drivers_out,
            r2=result.r2,
            recommendation=insight.recommendation,
            model_type=result.model_type,  # type: ignore[arg-type]
            decision_trace=trace,
        )

        # Timing check
        elapsed = time.perf_counter() - t_start
        logger.info("/analyze completed in %.3fs", elapsed)
        if elapsed > 1.8:
            logger.warning(
                "/analyze latency %.3fs is approaching the 2s budget!", elapsed
            )

        # ---------------------------------------------------------------
        # Step 10: Async Supabase persistence (fire-and-forget)
        # ---------------------------------------------------------------
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
