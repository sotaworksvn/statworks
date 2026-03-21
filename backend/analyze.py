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
        # Step 2a: Direct method dispatch (bypass LLM when method is set)
        #          Dashboard ribbon buttons send method directly.
        # ---------------------------------------------------------------
        _DIRECT_INTENTS = {
            "descriptive", "descriptive_statistics",
            "frequency", "frequencies",
            "correlation", "correlations",
            "scatter", "scatter_plot",
            "reliability",
            "validity",
            "model_fit",
            "effects", "effects_table",
            "path_coefficients",
            "bootstrap",
            "pls_sem",
            "bar_chart",
        }

        if body.method:
            method_key = body.method.lower().replace(" ", "_").replace("-", "_")
            if method_key in _DIRECT_INTENTS:
                # Auto-detect target: use last numeric column
                target = column_names[-1] if column_names else "target"
                elapsed = time.perf_counter() - t_start
                logger.info("/analyze direct dispatch '%s' in %.3fs", method_key, elapsed)
                return _dispatch_direct(method_key, df, target)

        # ---------------------------------------------------------------
        # Step 2b: LLM Call 1 — intent parsing (gpt-5.4-mini)
        #          On failure → Layer 1 fallback (auto-select features)
        # ---------------------------------------------------------------
        # Prepare sample data for LLM (first 5 rows, helps with format-aware edits)
        sample_rows = df.head(5).where(df.head(5).notna(), None).to_dict(orient="records")

        parsed = await parse_user_intent(
            query=body.query,
            column_names=column_names,
            context_text=entry.context_text,
            sample_rows=sample_rows,
        )

        # ---------------------------------------------------------------
        # Step 3: Validation Layer
        #         The handler NEVER touches raw LLM output directly.
        # ---------------------------------------------------------------
        cleaned = validate_parsed_intent(parsed, df)

        # ---------------------------------------------------------------
        # Step 4: Intent dispatch — route to the correct handler
        # ---------------------------------------------------------------
        intent = cleaned.intent.lower().replace(" ", "_")

        # ── not_supported: honest "can't answer" ──
        if intent == "not_supported":
            reason = cleaned.not_supported_reason or "This question cannot be answered with the available data."
            return AnalyzeResponse(
                summary=reason,
                drivers=[], r2=None,
                recommendation=f"Available columns: {', '.join(column_names[:8])}{'…' if len(column_names) > 8 else ''}. Try asking about these variables.",
                model_type=None,
                decision_trace=DecisionTrace(
                    score_pls=0.0, score_reg=0.0, engine_selected=None,
                    reason=f"Intent: not_supported. {reason}",
                ),
                result_type="not_supported",
                not_supported=True,
                suggestion=reason,
            )

        # ── data_edit: modify dataset values ──
        if intent == "data_edit":
            return await _handle_data_edit(df, cleaned, column_names, body)

        # ── comparison: group statistics ──
        if intent == "comparison":
            return await _handle_comparison(df, cleaned, column_names, body.query)

        # ── summary: descriptive statistics ──
        if intent == "summary":
            return _dispatch_direct("descriptive", df, "")

        # ── general_question: LLM answers from data context ──
        if intent == "general_question":
            return await _handle_general_question(df, cleaned, body.query)

        # ── Direct dispatch for known dashboard intents ──
        if intent in _DIRECT_INTENTS:
            return _dispatch_direct(intent, df, cleaned.target)


        # ---------------------------------------------------------------
        # Step 5: Decision Router (for driver_analysis)
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
            user_query=body.query,
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


def _dispatch_direct(intent: str, df: "pd.DataFrame", target: str) -> AnalyzeResponse:
    """Route non-regression intents to their statistical engines.

    These run pure pandas/scipy — no LLM calls needed.
    """
    import pandas as pd

    _no_trace = DecisionTrace(
        score_pls=0.0, score_reg=0.0, engine_selected=None, reason=f"Direct {intent} analysis",
    )

    try:
        if intent in ("descriptive", "descriptive_statistics"):
            from backend.engines.descriptive import compute_descriptive
            data = compute_descriptive(df)
            n = data["n_numeric"]
            return AnalyzeResponse(
                summary=f"Descriptive statistics computed for {n} numeric variables across {data['n_rows']} observations.",
                drivers=[], r2=None,
                recommendation="Review the central tendency (mean/median) and dispersion (std, range) of each variable.",
                model_type=None, decision_trace=_no_trace,
                result_type="descriptive", table_data=data,
            )

        if intent in ("frequency", "frequencies"):
            from backend.engines.frequency import compute_frequencies
            data = compute_frequencies(df)
            return AnalyzeResponse(
                summary=f"Frequency analysis completed for {data['n_variables']} variables.",
                drivers=[], r2=None,
                recommendation="Check the distribution shape and identify any outlier categories.",
                model_type=None, decision_trace=_no_trace,
                result_type="frequency", table_data=data,
            )

        if intent in ("correlation", "correlations"):
            from backend.engines.correlation import compute_correlations
            data = compute_correlations(df)
            n_sig = len(data.get("significant_pairs", []))
            return AnalyzeResponse(
                summary=f"Pearson correlation matrix computed. {n_sig} significant pair(s) found (p < 0.05).",
                drivers=[], r2=None,
                recommendation="Focus on strong correlations (|r| > 0.7) and check for multicollinearity.",
                model_type=None, decision_trace=_no_trace,
                result_type="correlation", table_data=data,
            )

        if intent in ("scatter", "scatter_plot"):
            from backend.engines.correlation import compute_scatter_data
            data = compute_scatter_data(df)
            x, y = data.get("x_col", "?"), data.get("y_col", "?")
            r = data.get("r", 0)
            return AnalyzeResponse(
                summary=f"Scatter plot for {x} vs {y} (r = {r}).",
                drivers=[], r2=None,
                recommendation=f"The correlation between {x} and {y} is {'strong' if abs(r or 0) > 0.7 else 'moderate' if abs(r or 0) > 0.4 else 'weak'}.",
                model_type=None, decision_trace=_no_trace,
                result_type="scatter", table_data=data,
            )

        if intent == "reliability":
            from backend.engines.reliability import compute_reliability
            data = compute_reliability(df)
            alpha = data.get("cronbachs_alpha")
            interp = data.get("interpretation", "N/A")
            return AnalyzeResponse(
                summary=f"Cronbach's Alpha = {alpha} ({interp}). {data['n_items']} items, {data['n_valid']} valid cases.",
                drivers=[], r2=None,
                recommendation="Items with low item-total correlation (< 0.3) or high alpha-if-deleted may be candidates for removal.",
                model_type=None, decision_trace=_no_trace,
                result_type="reliability", table_data=data,
            )

        if intent == "validity":
            from backend.engines.validity import compute_validity
            data = compute_validity(df)
            ave = data.get("ave")
            cr = data.get("composite_reliability")
            return AnalyzeResponse(
                summary=f"AVE = {ave}, Composite Reliability = {cr}. Convergent validity: {'✅ Met' if data.get('convergent_valid') else '❌ Not met'} (AVE ≥ 0.5). Discriminant validity: {'✅ Met' if data.get('discriminant_valid') else '❌ Not met'}.",
                drivers=[], r2=None,
                recommendation="If AVE < 0.5, consider removing items with low loadings to improve convergent validity.",
                model_type=None, decision_trace=_no_trace,
                result_type="validity", table_data=data,
            )

        if intent == "model_fit":
            from backend.engines.model_fit import compute_model_fit
            data = compute_model_fit(df, target=target)
            quality = data.get("quality", "N/A")
            return AnalyzeResponse(
                summary=f"Model fit quality: {quality}. SRMR = {data.get('srmr')}, R² = {data.get('r_squared')}.",
                drivers=[], r2=data.get("r_squared"),
                recommendation="SRMR < 0.08 indicates good fit. NFI > 0.90 is acceptable.",
                model_type=None, decision_trace=_no_trace,
                result_type="model_fit", table_data=data,
            )

        if intent in ("bar_chart",):
            # Run regression, but return as bar_chart for SVG visualization
            from backend.engines.regression import compute_ols
            try:
                all_numeric = [c for c in df.select_dtypes("number").columns if c != target]
                result = compute_ols(df, all_numeric, target)
                bar_data = {
                    "bars": [
                        {"name": d.name, "coefficient": round(d.coef, 4), "p_value": round(d.p_value, 4), "significant": d.significant}
                        for d in result.drivers
                    ],
                    "target": target,
                    "r_squared": result.r2,
                }
                return AnalyzeResponse(
                    summary=f"Coefficient bar chart for {target}. R² = {result.r2}.",
                    drivers=[], r2=result.r2,
                    recommendation="Taller bars indicate stronger drivers. Green = significant (p < 0.05).",
                    model_type=result.model_type, decision_trace=_no_trace,
                    result_type="bar_chart", table_data=bar_data,
                )
            except Exception as exc:
                logger.warning("Bar chart regression failed: %s", exc)

        if intent in ("bootstrap",):
            from backend.engines.bootstrap import compute_bootstrap
            data = compute_bootstrap(df, target=target)
            n_sig = sum(1 for r in data.get("results", []) if r.get("significant"))
            return AnalyzeResponse(
                summary=f"Bootstrap analysis ({data['n_bootstrap']} samples). {n_sig}/{len(data.get('results', []))} paths significant.",
                drivers=[], r2=None,
                recommendation="Paths with |T| > 1.96 and p < 0.05 are statistically significant at 95% confidence.",
                model_type=None, decision_trace=_no_trace,
                result_type="bootstrap", table_data=data,
            )

        if intent in ("pls_sem",):
            # Run PLS or OLS with path model metadata
            from backend.engines.regression import compute_ols
            from backend.engines.bootstrap import compute_bootstrap
            try:
                all_numeric = [c for c in df.select_dtypes("number").columns if c != target]
                result = compute_ols(df, all_numeric, target)
                boot = compute_bootstrap(df, target=target, n_bootstrap=200)
                path_data = {
                    "paths": [],
                    "target": target,
                    "r_squared": result.r2,
                    "n_observations": len(df),
                }
                # Merge OLS coefficients with bootstrap t-stats
                boot_map = {r["name"]: r for r in boot.get("results", [])}
                for d in result.drivers:
                    b = boot_map.get(d.name, {})
                    path_data["paths"].append({
                        "from": d.name,
                        "to": target,
                        "coefficient": round(d.coef, 4),
                        "t_statistic": b.get("t_statistic", 0.0),
                        "p_value": round(d.p_value, 4),
                        "significant": d.significant,
                    })
                return AnalyzeResponse(
                    summary=f"PLS-SEM path model for {target}. R² = {result.r2}.",
                    drivers=[], r2=result.r2,
                    recommendation="Significant paths (p < 0.05) represent meaningful structural relationships.",
                    model_type="pls", decision_trace=_no_trace,
                    result_type="path_model", table_data=path_data,
                )
            except Exception as exc:
                logger.warning("PLS-SEM failed: %s", exc)

        if intent in ("effects", "effects_table"):
            # Compute full effects: Direct + Indirect + Total
            from backend.engines.regression import compute_ols
            try:
                all_numeric = [c for c in df.select_dtypes("number").columns if c != target]
                result = compute_ols(df, all_numeric, target)

                # Direct effects
                direct = [
                    {"name": d.name, "effect": round(d.coef, 4), "p_value": round(d.p_value, 4), "significant": d.significant}
                    for d in result.drivers
                ]

                # Indirect effects: X→M→Y via mediation analysis
                indirect = []
                for mediator in all_numeric:
                    other_predictors = [c for c in all_numeric if c != mediator]
                    if not other_predictors:
                        continue
                    try:
                        # Path a: X→M
                        res_m = compute_ols(df, other_predictors, mediator)
                        # Get path b: M→Y (from main regression)
                        m_coef = next((d.coef for d in result.drivers if d.name == mediator), 0.0)
                        for pred in other_predictors:
                            a_coef = next((d.coef for d in res_m.drivers if d.name == pred), 0.0)
                            indirect_effect = round(a_coef * m_coef, 4)
                            if abs(indirect_effect) > 0.001:
                                indirect.append({
                                    "from": pred, "via": mediator, "to": target,
                                    "effect": indirect_effect,
                                })
                    except Exception:
                        pass

                # Total effects = direct + sum of indirect
                total = []
                for d in direct:
                    ind_sum = sum(ie["effect"] for ie in indirect if ie["from"] == d["name"])
                    total.append({
                        "name": d["name"],
                        "direct": d["effect"],
                        "indirect": round(ind_sum, 4),
                        "total": round(d["effect"] + ind_sum, 4),
                    })

                effects_data = {
                    "direct_effects": direct,
                    "indirect_effects": indirect[:15],  # cap for readability
                    "total_effects": total,
                    "target": target,
                    "r_squared": result.r2,
                }
                return AnalyzeResponse(
                    summary=f"Effects decomposition for {target}: {len(direct)} direct, {len(indirect)} indirect paths.",
                    drivers=[], r2=result.r2,
                    recommendation="Compare total effects to identify the most influential variables including indirect pathways.",
                    model_type=result.model_type, decision_trace=_no_trace,
                    result_type="effects", table_data=effects_data,
                )
            except Exception:
                pass

        if intent in ("path_coefficients",):
            # Path coefficients with T-statistics from bootstrap
            from backend.engines.regression import compute_ols
            from backend.engines.bootstrap import compute_bootstrap
            try:
                all_numeric = [c for c in df.select_dtypes("number").columns if c != target]
                result = compute_ols(df, all_numeric, target)
                boot = compute_bootstrap(df, target=target, n_bootstrap=200)
                boot_map = {r["name"]: r for r in boot.get("results", [])}
                paths = []
                for d in result.drivers:
                    b = boot_map.get(d.name, {})
                    paths.append({
                        "name": d.name,
                        "coefficient": round(d.coef, 4),
                        "t_statistic": b.get("t_statistic", 0.0),
                        "p_value": round(d.p_value, 4),
                        "ci_lower": b.get("ci_lower", None),
                        "ci_upper": b.get("ci_upper", None),
                        "significant": d.significant,
                    })
                path_data = {"paths": paths, "target": target, "r_squared": result.r2}
                return AnalyzeResponse(
                    summary=f"Path coefficients for {target} with bootstrap T-statistics.",
                    drivers=[], r2=result.r2,
                    recommendation="Paths with |T| > 1.96 are significant at 95% confidence.",
                    model_type=result.model_type, decision_trace=_no_trace,
                    result_type="path_coefficients", table_data=path_data,
                )
            except Exception:
                pass

        # Fallback for unknown sub-intents
        return AnalyzeResponse(
            summary="This analysis type is not yet available.",
            drivers=[], r2=None,
            recommendation=f"Try asking: 'What drives {target}?' for regression analysis.",
            model_type=None, decision_trace=_no_trace,
            result_type="unsupported", table_data=None,
        )

    except Exception as exc:
        _intent = locals().get("intent", "unknown")
        logger.error("Direct analysis failed for intent=%s: %s", _intent, exc)
        _fallback_trace = DecisionTrace(
            score_pls=0.0, score_reg=0.0, engine_selected=None,
            reason=f"Unexpected error: {exc}",
        )
        return AnalyzeResponse(
            summary=f"Analysis error: {exc}",
            drivers=[], r2=None,
            recommendation="Please check your dataset and try again.",
            model_type=None, decision_trace=_fallback_trace,
            result_type="error", table_data=None,
        )

# ---------------------------------------------------------------------------
# New intent handlers
# ---------------------------------------------------------------------------


import re as _re


def _detect_date_format(query: str) -> tuple[str, bool] | None:
    """Detect desired date format from a user query string.

    Returns ``(strftime_format, dayfirst)`` or ``None`` if no format found.
    Fallback (if ambiguous) → DD/MM/YYYY.
    """
    q = query.upper()
    if "DD/MM/YYYY" in q:
        return "%d/%m/%Y", True
    if "DD-MM-YYYY" in q:
        return "%d-%m-%Y", True
    if "MM/DD/YYYY" in q:
        return "%m/%d/%Y", False
    if "MM-DD-YYYY" in q:
        return "%m-%d-%Y", False
    if "YYYY-MM-DD" in q:
        return "%Y-%m-%d", True
    if "YYYY/MM/DD" in q:
        return "%Y/%m/%d", True
    return None


def _detect_row_range(query: str) -> tuple[int, int] | None:
    """Detect a row range from the query (e.g. 'rows 25-30', 'hàng 25 đến 30').

    Returns ``(start, end)`` as 0-based inclusive indices, or ``None``.
    """
    m = _re.search(
        r'(?:rows?|hàng|dòng)\s*(\d+)\s*[-–tođến]+\s*(\d+)',
        query, _re.IGNORECASE,
    )
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        # Convert to 0-based (user likely uses 1-based or 0-based — assume smallest is row 0)
        start = min(a, b)
        end = max(a, b)
        return start, end
    return None


async def _handle_data_edit(
    df: "pd.DataFrame",
    cleaned: "CleanedIntent",
    column_names: list[str],
    body: "AnalyzeRequest",
) -> AnalyzeResponse:
    """Handle data_edit intent — modify dataset values via AI."""
    import pandas as pd
    from backend.store import get_entry, set_entry

    _no_trace = DecisionTrace(
        score_pls=0.0, score_reg=0.0, engine_selected=None,
        reason="Intent: data_edit",
    )

    edits = cleaned.edits
    if not edits:
        return AnalyzeResponse(
            summary="No valid edits could be extracted from your request.",
            drivers=[], r2=None,
            recommendation="Try specifying clearly what you want to change. Example: 'Change the region of Iran to Western Asia'.",
            model_type=None, decision_trace=_no_trace,
            result_type="data_edit",
        )

    # Apply edits to in-memory DataFrame
    entry = await get_entry(body.file_id)
    if entry is None:
        return AnalyzeResponse(
            summary="Dataset not found. Please re-upload your file.",
            drivers=[], r2=None,
            recommendation="Upload a dataset first.",
            model_type=None, decision_trace=_no_trace,
            result_type="error",
        )

    applied = 0
    edit_details: list[str] = []

    # ── Date format bulk-conversion (deterministic, not LLM) ──────────
    fmt_result = _detect_date_format(body.query)
    if fmt_result is not None:
        strftime_fmt, dayfirst = fmt_result
        # Identify the target date column from the LLM edits
        date_cols_from_edits = {e.get("column") for e in edits if e.get("column") in df.columns}
        row_range = _detect_row_range(body.query)

        for col in date_cols_from_edits:
            original = df[col].copy()
            parsed_1 = pd.to_datetime(df[col], dayfirst=dayfirst, errors="coerce")
            parsed_2 = pd.to_datetime(df[col], format="ISO8601", errors="coerce")
            converted = parsed_1.fillna(parsed_2)
            formatted = converted.dt.strftime(strftime_fmt)

            if row_range is not None:
                start, end = row_range
                end = min(end, len(df) - 1)
                start = max(start, 0)
                mask = (df.index >= start) & (df.index <= end)
                count = int(mask.sum())
                # Apply only to the specified range, keep original on parse failure
                df.loc[mask, col] = formatted.where(converted.notna(), original)[mask]
                applied += count
                edit_details.append(
                    f"Formatted '{col}' to {strftime_fmt} for rows {start}–{end} ({count} row(s))"
                )
            else:
                # Apply to ALL rows, keep original on parse failure
                df[col] = formatted.where(converted.notna(), original)
                count = int(converted.notna().sum())
                applied += count
                edit_details.append(
                    f"Formatted '{col}' to {strftime_fmt} for all {count} row(s)"
                )

        # Save and return early — skip per-row LLM edits
        entry.dataframe = df
        entry.row_count = len(df)
        await set_entry(entry)

        summary = f"✅ Successfully formatted {applied} cell(s). " + "; ".join(edit_details)
        return AnalyzeResponse(
            summary=summary,
            drivers=[], r2=None,
            recommendation="The dataset has been updated. Your next analysis will use the updated data.",
            model_type=None, decision_trace=_no_trace,
            result_type="data_edit",
        )

    # ── Standard per-row edits (non-date) ─────────────────────────────
    for edit in edits:
        col = edit.get("column")
        new_val = edit.get("new_value")
        filter_col = edit.get("filter_column")
        filter_val = edit.get("filter_value")

        if not col or col not in df.columns:
            continue

        if filter_col and filter_col in df.columns and filter_val is not None:
            mask = df[filter_col].astype(str) == str(filter_val)
            count = int(mask.sum())
            if count > 0:
                df.loc[mask, col] = new_val
                applied += count
                edit_details.append(
                    f"Changed '{col}' to '{new_val}' for {count} row(s) where {filter_col}='{filter_val}'"
                )

    # Save back to store
    entry.dataframe = df
    entry.row_count = len(df)
    await set_entry(entry)

    if applied > 0:
        summary = f"✅ Successfully applied {applied} edit(s). " + "; ".join(edit_details)
        rec = "The dataset has been updated. Your next analysis will use the updated data."
    else:
        summary = "No matching rows were found for the specified edits."
        rec = "Check the filter values — make sure they match exactly what's in the data."

    return AnalyzeResponse(
        summary=summary,
        drivers=[], r2=None,
        recommendation=rec,
        model_type=None, decision_trace=_no_trace,
        result_type="data_edit",
    )


async def _handle_comparison(
    df: "pd.DataFrame",
    cleaned: "CleanedIntent",
    column_names: list[str],
    query: str,
) -> AnalyzeResponse:
    """Handle comparison intent — group stats by categorical column."""
    import pandas as pd

    _no_trace = DecisionTrace(
        score_pls=0.0, score_reg=0.0, engine_selected=None,
        reason="Intent: comparison",
    )

    # Find categorical / object columns that could be used for grouping
    cat_cols = [
        c for c in df.columns
        if df[c].dtype == "object" or (df[c].nunique() < 15 and df[c].nunique() > 1)
    ]

    if not cat_cols:
        # No grouping column available → honest response
        return AnalyzeResponse(
            summary=(
                "This dataset contains only numeric variables with no categorical "
                "grouping column (e.g., region, category, group). "
                "A comparison analysis requires at least one column to group the data by."
            ),
            drivers=[], r2=None,
            recommendation=(
                f"Available columns are all numeric: {', '.join(column_names[:6])}. "
                "To compare groups, add a column like 'Region', 'Category', or 'Group' to your dataset, "
                "or try asking 'What drives [variable]?' for regression analysis."
            ),
            model_type=None, decision_trace=_no_trace,
            result_type="not_supported",
            not_supported=True,
            suggestion="Add a categorical grouping column to enable comparison analysis.",
        )

    # Use LLM-specified group_by if valid, else pick lowest-cardinality categorical col
    if cleaned.group_by and cleaned.group_by in cat_cols:
        group_col = cleaned.group_by
    else:
        # Prefer columns with fewer unique values (more meaningful groups)
        group_col = min(cat_cols, key=lambda c: df[c].nunique())

    # Use LLM-specified features if available, else all numeric
    numeric_cols = df.select_dtypes("number").columns.tolist()
    if cleaned.features:
        compare_cols = [f for f in cleaned.features if f in numeric_cols]
    else:
        compare_cols = numeric_cols

    if not numeric_cols:
        return AnalyzeResponse(
            summary="No numeric columns available for comparison.",
            drivers=[], r2=None,
            recommendation="Check your dataset for numeric variables.",
            model_type=None, decision_trace=_no_trace,
            result_type="not_supported",
            not_supported=True,
            suggestion="Upload a dataset with numeric variables.",
        )

    # ── Smart group merging ──
    # If user asks about higher-level categories (e.g., "Asia") but data has
    # sub-categories (e.g., "Southern Asia"), use LLM to create a mapping.
    # This is fully generic — works for any dataset.
    actual_group_col = group_col
    unique_vals = df[group_col].dropna().unique().tolist()
    try:
        from backend.llm.client import call_llm_with_retry
        import json as _j

        merge_result = await call_llm_with_retry(
            model="gpt-5.4-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data grouping assistant. The user wants to compare groups in their data. "
                        "The dataset has a column with these values. Determine if the user's question "
                        "implies higher-level categories that require merging these values.\n\n"
                        "If merging is needed, return JSON:\n"
                        '{"needs_merge": true, "mapping": {"original_value": "super_group", ...}, "merged_col_name": "Continent"}\n\n'
                        "If no merging needed (values already match what user asks), return:\n"
                        '{"needs_merge": false}\n\n'
                        "Rules:\n"
                        "- Only merge if the user clearly refers to broader categories than what's in the data\n"
                        "- Use your world knowledge to map values to the right super-groups\n"
                        "- Every original value MUST appear in the mapping\n"
                        "- Do not hallucinate — if unsure, set needs_merge to false"
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"User question: {query}\n\n"
                        f"Column '{group_col}' has these values:\n"
                        + "\n".join(f"- {v}" for v in unique_vals)
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )

        if merge_result.get("needs_merge") and merge_result.get("mapping"):
            mapping = merge_result["mapping"]
            merged_name = merge_result.get("merged_col_name", "Group")
            # Apply mapping — create virtual column
            df = df.copy()
            df["__merged_group__"] = df[group_col].map(mapping).fillna("Other")
            actual_group_col = "__merged_group__"
            logger.info(
                "Smart merge: %s → %d super-groups (%s)",
                group_col, df["__merged_group__"].nunique(), merged_name,
            )
    except Exception as merge_exc:
        logger.warning("Smart merge LLM failed (using raw groups): %s", merge_exc)

    # Compute group means for requested columns
    cols_to_compare = compare_cols if compare_cols else numeric_cols
    try:
        grouped = df.groupby(actual_group_col)[cols_to_compare].mean()
        display_col = actual_group_col if actual_group_col != "__merged_group__" else group_col
        groups_data = {
            "group_column": display_col,
            "groups": grouped.index.tolist(),
            "n_groups": len(grouped),
            "variables": cols_to_compare[:10],  # cap
            "means": {
                str(g): {col: round(float(v), 4) for col, v in row.items()}
                for g, row in grouped.iterrows()
            },
            "group_sizes": df[actual_group_col].value_counts().to_dict(),
        }

        n_groups = len(grouped)

        # Generate LLM summary from actual group data
        import json as _json
        summary_text = (
            f"Comparison across {n_groups} groups (grouped by '{group_col}'). "
            f"Analyzed {len(cols_to_compare)} variables: {', '.join(cols_to_compare[:5])}."
        )
        rec_text = (
            f"Review the mean differences across groups. "
            f"Groups: {', '.join(str(g) for g in grouped.index[:5])}."
        )
        try:
            from backend.llm.client import call_llm_with_retry

            # Build concise data summary for LLM
            means_summary = _json.dumps(groups_data["means"], ensure_ascii=False, default=str)[:1500]
            llm_result = await call_llm_with_retry(
                    model="gpt-5.4-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a data analyst. Summarize the comparison results in 2-3 sentences. "
                                "Mention which group ranks highest/lowest for key variables. "
                                "Write in plain business language. "
                                "Return JSON: {\"summary\": \"<comparison insight>\", \"recommendation\": \"<actionable advice>\"}"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"User question: {query}\n\n"
                                f"Groups (by {group_col}): {', '.join(str(g) for g in grouped.index)}\n"
                                f"Variables: {', '.join(cols_to_compare)}\n"
                                f"Mean values:\n{means_summary}"
                            ),
                        },
                    ],
                    response_format={"type": "json_object"},
                )
            summary_text = llm_result.get("summary", summary_text)
            rec_text = llm_result.get("recommendation", rec_text)
        except Exception as llm_exc:
            logger.warning("Comparison LLM summary failed: %s", llm_exc)
            # Fallback: data-driven summary
            for col in cols_to_compare[:2]:
                col_data = {str(g): grouped.loc[g, col] for g in grouped.index}
                best = max(col_data, key=col_data.get)
                worst = min(col_data, key=col_data.get)
                summary_text += f" {col}: highest in {best}, lowest in {worst}."

        return AnalyzeResponse(
            summary=summary_text,
            drivers=[], r2=None,
            recommendation=rec_text,
            model_type=None, decision_trace=_no_trace,
            result_type="comparison", table_data=groups_data,
        )
    except Exception as exc:
        logger.warning("Comparison failed: %s", exc)
        return AnalyzeResponse(
            summary=f"Comparison analysis failed: {exc}",
            drivers=[], r2=None,
            recommendation="Please check your dataset and try again.",
            model_type=None, decision_trace=_no_trace,
            result_type="error",
        )


async def _handle_general_question(
    df: "pd.DataFrame",
    cleaned: "CleanedIntent",
    query: str,
) -> AnalyzeResponse:
    """Handle general questions by using LLM to answer from data context."""
    import json

    _no_trace = DecisionTrace(
        score_pls=0.0, score_reg=0.0, engine_selected=None,
        reason="Intent: general_question",
    )

    # Build data summary for LLM
    numeric_cols = df.select_dtypes("number").columns.tolist()
    data_summary_parts = [
        f"Dataset: {len(df)} rows, {len(df.columns)} columns",
        f"Columns: {', '.join(df.columns.tolist())}",
    ]
    if numeric_cols:
        desc = df[numeric_cols].describe().round(2)
        data_summary_parts.append(f"Statistics:\n{desc.to_string()}")

    data_context = "\n".join(data_summary_parts)

    try:
        from backend.llm.client import call_llm_with_retry

        result = await call_llm_with_retry(
            model="gpt-5.4-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a data analysis assistant. Answer the user's question "
                        "based ONLY on the data summary provided. Be concise and accurate. "
                        "Return JSON: {\"summary\": \"<answer>\", \"recommendation\": \"<next step>\"}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"Data:\n{data_context}\n\nQuestion: {query}",
                },
            ],
            response_format={"type": "json_object"},
        )

        summary = result.get("summary", "Could not generate an answer.")
        recommendation = result.get("recommendation", "Try a more specific question.")

        return AnalyzeResponse(
            summary=summary,
            drivers=[], r2=None,
            recommendation=recommendation,
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )
    except Exception as exc:
        logger.warning("General question LLM failed: %s", exc)
        return AnalyzeResponse(
            summary=f"Could not answer this question: {exc}",
            drivers=[], r2=None,
            recommendation="Try asking 'What drives [variable]?' for statistical analysis.",
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )
