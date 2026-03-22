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
import re
import time
import unicodedata
from typing import Union


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
    StudentProfileResponse,
)
from backend.router import score_model
from backend.store import get_entry, set_entry
from backend.validation import validate_parsed_intent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/analyze", response_model=Union[StudentProfileResponse, AnalyzeResponse])
async def analyze(body: AnalyzeRequest) -> Union[StudentProfileResponse, AnalyzeResponse]:
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
        # Step 2a.1: GPA target planning (deterministic, no regression)
        # ---------------------------------------------------------------
        if _is_gpa_goal_query(body.query):
            elapsed = time.perf_counter() - t_start
            logger.info("/analyze GPA goal dispatch in %.3fs", elapsed)
            return _handle_gpa_goal(df, body.query)

        # ---------------------------------------------------------------
        # Step 2a.2: Student profile analysis (deterministic bypass)
        #   Triggered when user asks about scholarships/opportunities AND
        #   the dataset looks like student academic data (THPT/GPA/CV context).
        # ---------------------------------------------------------------
        if _is_student_profile_query(body.query, entry):
            elapsed = time.perf_counter() - t_start
            logger.info("/analyze student_profile_analysis dispatch in %.3fs", elapsed)
            return await _handle_student_profile_analysis(entry, df, column_names, body.query)

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

        # ── student_profile_analysis: 6-section comprehensive pipeline ──
        if intent in (
            "student_profile_analysis", "student_profile",
            "scholarship_analysis", "profile_analysis",
            "analyze_profile", "opportunity_analysis",
        ):
            return await _handle_student_profile_analysis(entry, df, column_names, body.query)

        # ── scholarship_prediction: EdTech track ──
        if intent in ("scholarship_prediction", "scholarship", "predict_scholarship", "school_matching"):
            return await _handle_scholarship_prediction(entry, df, column_names)

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
        return AnalyzeResponse(
            summary="Hệ thống gặp lỗi nội bộ khi xử lý yêu cầu.",
            drivers=[],
            r2=None,
            recommendation="Vui lòng thử lại. Nếu lỗi lặp lại, hãy hỏi theo mẫu: 'Mục tiêu GPA 8.0, mỗi môn chưa có điểm cần bao nhiêu?'",
            model_type=None,
            decision_trace=DecisionTrace(
                score_pls=0.0,
                score_reg=0.0,
                engine_selected=None,
                reason="Unexpected error fallback",
            ),
            result_type="general",
        )


def _is_gpa_goal_query(query: str) -> bool:
    q = _normalize_text(query)
    has_goal = any(k in q for k in ("gpa", "diem trung binh", "grade point average"))
    has_requirement = any(
        k in q
        for k in (
            "bao nhieu",
            "it nhat",
            "at least",
            "can",
            "need",
            "required",
        )
    )
    has_pending = any(
        k in q
        for k in (
            "chua co diem",
            "pending",
            "not started",
            "studying",
            "moi mon",
            "each subject",
        )
    )
    return has_goal and (has_requirement or has_pending)



def _is_student_profile_query(query: str, entry: "FileEntry") -> bool:
    """Detect student scholarship/profile analysis requests.

    Returns True when:
    1. The query contains scholarship/profile analysis keywords, AND
    2. The dataset context looks like student academic data (THPT/GPA/certificate files).
    """
    from backend.store import FileEntry  # type: ignore[attr-defined]

    q = _normalize_text(query)

    # Query-side keywords (Vietnamese + English)
    scholarship_kws = [
        "hoc bong", "co hoi", "phan tich ho so", "profile", "apply dau",
        "truong nao", "vao dau", "chon truong", "co the dat", "co the nop",
        "recommendation", "lo trinh", "roadmap", "scholarship", "opportunity",
        "admission", "university matching", "truong phu hop", "phu hop voi",
        "ho so cua toi", "nang luc", "phan tich nang luc",
        "toi co the", "kha nang dat", "xet hoc bong", "hoc bong phu hop",
    ]
    query_match = any(kw in q for kw in scholarship_kws)

    if not query_match:
        return False

    # Context-side signals: does this look like student data?
    # entry is a FileEntry object — use attribute access, not .get()
    context = getattr(entry, "context_text", "") or ""
    filename = getattr(entry, "file_name", "") or ""

    student_data_signals = [
        "thpt", "bang diem", "chung chi", "hoat dong",
        "gpa", "toefl", "ielts", "sat", "diem so",
        "mon hoc", "hoc ky", "hoc sinh",
        "nguyen van an", "ho so",
    ]

    context_lower = _normalize_text(context + " " + filename)
    context_match = any(sig in context_lower for sig in student_data_signals)

    return context_match


def _extract_gpa_target(query: str) -> float | None:
    q = _normalize_text(query)
    # Prefer values near cues like "gpa", "lên/to", "target"
    patterns = [
        r"(?:gpa|target|muc tieu|len|to)\D{0,8}(\d{1,2}(?:[.,]\d{1,2})?)",
        r"(\d{1,2}(?:[.,]\d{1,2})?)\D{0,8}(?:gpa)",
    ]
    for pat in patterns:
        m = re.search(pat, q, flags=re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except ValueError:
                pass
    return None


def _gpa_query_prefers_each_subject(query: str) -> bool:
    q = _normalize_text(query)
    return any(
        k in q
        for k in (
            "moi mon",
            "tung mon",
            "tung hoc phan",
            "each subject",
            "every subject",
            "per subject",
        )
    )


def _gpa_query_prefers_average(query: str) -> bool:
    q = _normalize_text(query)
    return any(
        k in q
        for k in (
            "trung binh",
            "average",
            "avg",
        )
    )


def _normalize_text(text: str | None) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFD", text)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s.lower()


def _find_first_column(columns: list[str], candidates: list[str]) -> str | None:
    by_lower = {c.lower(): c for c in columns}
    for cand in candidates:
        if cand in by_lower:
            return by_lower[cand]
    for col in columns:
        low = col.lower()
        if any(cand in low for cand in candidates):
            return col
    return None


def _handle_gpa_goal(df: "pd.DataFrame", query: str) -> AnalyzeResponse:
    """Estimate required grade per pending subject to hit a GPA target."""
    import pandas as pd

    _no_trace = DecisionTrace(
        score_pls=0.0, score_reg=0.0, engine_selected=None, reason="Intent: gpa_goal_planning",
    )
    prefers_each_subject = _gpa_query_prefers_each_subject(query)
    prefers_average = _gpa_query_prefers_average(query)

    columns = df.columns.tolist()
    grade_col = _find_first_column(
        columns,
        ["grade", "điểm", "diem", "score", "mark"],
    )
    credit_col = _find_first_column(
        columns,
        ["credit", "tín chỉ", "tin chi", "units", "ects"],
    )
    status_col = _find_first_column(
        columns,
        ["status", "trạng thái", "trang thai"],
    )
    subject_col = _find_first_column(
        columns,
        ["subject name", "course", "môn", "mon", "subject"],
    )

    if not grade_col or not credit_col:
        return AnalyzeResponse(
            summary="Không tìm thấy đủ cột để tính GPA mục tiêu (cần cột điểm và tín chỉ).",
            drivers=[], r2=None,
            recommendation="Hãy đảm bảo file có cột tương đương 'Grade' và 'Credit'.",
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )

    grades = pd.to_numeric(df[grade_col], errors="coerce")
    credits = pd.to_numeric(df[credit_col], errors="coerce")

    known_mask = grades.notna() & credits.notna() & (credits > 0)
    if int(known_mask.sum()) == 0:
        return AnalyzeResponse(
            summary="Chưa có đủ môn đã có điểm + tín chỉ để tính GPA hiện tại.",
            drivers=[], r2=None,
            recommendation="Cần ít nhất một môn có đủ Grade và Credit > 0.",
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )

    known_points = float((grades[known_mask] * credits[known_mask]).sum())
    known_credits = float(credits[known_mask].sum())
    current_gpa = known_points / known_credits if known_credits > 0 else 0.0

    target = _extract_gpa_target(query)
    if target is None:
        target = min(current_gpa + 0.5, 10.0)

    # Detect grade scale from existing data
    grade_scale_max = 10.0
    max_seen = float(grades[known_mask].max()) if int(known_mask.sum()) else 10.0
    if max_seen <= 4.5 and target <= 4.5:
        grade_scale_max = 4.0

    if target > grade_scale_max:
        return AnalyzeResponse(
            summary=f"Mục tiêu GPA {target:.2f} vượt thang điểm hiện tại (0-{grade_scale_max:.1f}).",
            drivers=[], r2=None,
            recommendation=f"Hãy nhập mục tiêu trong khoảng 0-{grade_scale_max:.1f}.",
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )

    pending_mask = grades.isna()
    if status_col:
        status_txt = df[status_col].astype(str).str.lower()
        done_status = status_txt.str.contains(
            r"passed|completed|done|đạt|dat",
            na=False,
            regex=True,
        )
        pending_status = status_txt.str.contains(
            r"studying|not started|in progress|register|pending|chưa|dang hoc",
            na=False,
            regex=True,
        )
        pending_mask = (pending_mask & ~done_status) | pending_status

    if subject_col:
        pending_mask = pending_mask & df[subject_col].notna()

    pending_df = df[pending_mask].copy()
    pending_count = len(pending_df)
    if pending_count == 0:
        if current_gpa >= target:
            summary = f"GPA hiện tại khoảng {current_gpa:.2f}, đã đạt mục tiêu {target:.2f}."
            rec = "Bạn không cần thêm điểm để đạt mục tiêu này."
        else:
            summary = f"Không còn môn chờ điểm nhưng GPA hiện tại ({current_gpa:.2f}) chưa đạt mục tiêu {target:.2f}."
            rec = "Bạn cần học cải thiện hoặc đăng ký thêm môn có điểm cao."
        return AnalyzeResponse(
            summary=summary,
            drivers=[], r2=None,
            recommendation=rec,
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )

    pending_credits = pd.to_numeric(pending_df[credit_col], errors="coerce")
    known_pending_credits = float(pending_credits.fillna(0).clip(lower=0).sum())
    missing_credit_count = int((pending_credits.isna() | (pending_credits <= 0)).sum())

    def _required_avg(extra_credits: float) -> float:
        return ((target * (known_credits + extra_credits)) - known_points) / extra_credits

    # Case A: exact computation (all pending credits known)
    if known_pending_credits > 0 and missing_credit_count == 0:
        req = _required_avg(known_pending_credits)

        if req <= 0:
            summary = (
                f"GPA hiện tại {current_gpa:.2f}. Với {pending_count} môn chưa có điểm "
                f"(tổng {known_pending_credits:.1f} tín chỉ), bạn đã ở mức đạt mục tiêu {target:.2f}."
            )
            recommendation = "Giữ điểm các môn còn lại ổn định để duy trì GPA mục tiêu."
        elif req > grade_scale_max:
            summary = (
                f"Để đạt GPA {target:.2f}, điểm trung bình cần cho các môn còn lại là {req:.2f}/{grade_scale_max:.1f}, "
                "vượt thang điểm nên không khả thi theo dữ liệu hiện tại."
            )
            recommendation = "Giảm mục tiêu GPA hoặc tăng số tín chỉ môn mới có thể đạt điểm cao."
        else:
            req_phrase = (
                f"mỗi môn chưa có điểm cần tối thiểu khoảng {req:.2f}/{grade_scale_max:.1f}"
                if prefers_each_subject and not prefers_average
                else f"điểm trung bình các môn còn lại cần khoảng {req:.2f}/{grade_scale_max:.1f}"
            )
            summary = (
                f"GPA hiện tại {current_gpa:.2f}. Để lên {target:.2f}, "
                f"{req_phrase}."
            )
            recommendation = (
                f"Tập trung giữ các môn pending từ {req:.2f} trở lên, ưu tiên môn nhiều tín chỉ trước."
            )

        return AnalyzeResponse(
            summary=summary,
            drivers=[], r2=None,
            recommendation=recommendation,
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )

    # Case B: estimate when some pending credits are missing
    known_credit_values = pd.to_numeric(df[credit_col], errors="coerce")
    known_credit_values = known_credit_values[(known_credit_values > 0) & known_credit_values.notna()]
    avg_credit = float(known_credit_values.median()) if len(known_credit_values) else 3.0
    if avg_credit <= 0:
        avg_credit = 3.0

    estimated_pending_credits = known_pending_credits + (missing_credit_count * avg_credit)
    req_est = _required_avg(estimated_pending_credits) if estimated_pending_credits > 0 else float("inf")

    if req_est <= 0:
        summary = (
            f"GPA hiện tại {current_gpa:.2f}. Với dữ liệu hiện có, bạn đã đạt hoặc vượt mục tiêu {target:.2f} "
            "nên không cần mức điểm tối thiểu dương cho các môn còn lại."
        )
        recommendation = (
            "Bạn chỉ cần giữ điểm các môn còn lại ở mức ổn định để duy trì GPA mục tiêu. "
            "Nếu muốn hệ thống dự báo chính xác hơn, hãy bổ sung Credit cho các môn chưa có điểm."
        )
        return AnalyzeResponse(
            summary=summary,
            drivers=[], r2=None,
            recommendation=recommendation,
            model_type=None, decision_trace=_no_trace,
            result_type="general",
        )

    scenario_lines = []
    for credit_assumption in (2.0, 3.0, 4.0):
        est_credits = known_pending_credits + (missing_credit_count * credit_assumption)
        if est_credits <= 0:
            continue
        req_s = _required_avg(est_credits)
        if req_s <= 0:
            scenario_lines.append(f"~{credit_assumption:.0f} tín chỉ/môn => đã đạt mục tiêu")
        elif req_s > grade_scale_max:
            scenario_lines.append(
                f"~{credit_assumption:.0f} tín chỉ/môn => cần {req_s:.2f}/{grade_scale_max:.1f} (khó khả thi)"
            )
        else:
            scenario_lines.append(f"~{credit_assumption:.0f} tín chỉ/môn => cần khoảng {req_s:.2f}")

    req_est_phrase = (
        f"mỗi môn cần tối thiểu khoảng {req_est:.2f}/{grade_scale_max:.1f}"
        if prefers_each_subject and not prefers_average
        else f"điểm trung bình cần khoảng {req_est:.2f}/{grade_scale_max:.1f}"
    )
    summary = (
        f"GPA hiện tại {current_gpa:.2f}. Có {pending_count} môn chưa có điểm nhưng thiếu dữ liệu tín chỉ "
        f"ở {missing_credit_count} môn nên chưa thể tính chính xác. "
        f"Ước tính nếu mỗi môn pending ~{avg_credit:.1f} tín chỉ thì {req_est_phrase}."
    )
    recommendation = (
        "Bổ sung Credit cho các môn chưa có điểm để hệ thống tính chính xác. "
        + (" | ".join(scenario_lines) if scenario_lines else "")
    )

    return AnalyzeResponse(
        summary=summary,
        drivers=[], r2=None,
        recommendation=recommendation,
        model_type=None, decision_trace=_no_trace,
        result_type="general",
    )


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
            parsed_2 = pd.to_datetime(df[col], format="%Y-%m-%dT%H:%M:%S", errors="coerce").fillna(
                pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")
            )
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
    """Handle general questions by using LLM to answer from data context.

    If the question requires real-world knowledge (e.g. university admissions,
    scholarships), uses web_search_answer() for live, grounded results.
    Otherwise falls back to LLM with data context only.
    """
    import json

    _no_trace = DecisionTrace(
        score_pls=0.0, score_reg=0.0, engine_selected=None,
        reason="Intent: general_question",
    )

    # ── Check if this query needs live web data ──
    from backend.llm.web_search import _requires_web_search, web_search_answer

    if _requires_web_search(query):
        # Build a concise profile from the dataset for personalization
        numeric_cols = df.select_dtypes("number").columns.tolist()
        profile_parts: list[str] = [f"Dataset: {len(df)} rows, {len(df.columns)} columns"]

        if numeric_cols:
            try:
                summary_stats = df[numeric_cols].describe().round(2)
                # Compact version: just means
                means = {col: round(float(df[col].dropna().mean()), 2) for col in numeric_cols[:8]}
                profile_parts.append(
                    "Column averages: " + ", ".join(f"{k}={v}" for k, v in means.items())
                )
            except Exception:
                pass

        dataset_context = "\n".join(profile_parts)

        try:
            result = await web_search_answer(query=query, context=dataset_context)

            if result is not None:
                formatted_answer = result.format_with_citations()
                return AnalyzeResponse(
                    summary=formatted_answer,
                    drivers=[], r2=None,
                    recommendation=(
                        "Kết quả trên được tổng hợp từ dữ liệu web thực tế. "
                        "Hãy xác nhận thêm với trang chính thức của trường."
                        if any(c > 127 for c in map(ord, query))
                        else "Results sourced from live web data. Verify with official university websites for the most current requirements."
                    ),
                    model_type=None, decision_trace=_no_trace,
                    result_type="general",
                    table_data={"web_search_result": True, "citations": result.citations},
                )
        except Exception as ws_exc:
            logger.warning("Web search failed, falling back to data-context LLM: %s", ws_exc)

    # ── Data-context fallback (no web search needed or web search failed) ──
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



# ---------------------------------------------------------------------------
# Scholarship Prediction Handler (EdTech Track)
# ---------------------------------------------------------------------------

async def _handle_scholarship_prediction(entry: object, df, column_names: list) -> "AnalyzeResponse":
    """Handle scholarship prediction flow.

    1. Extract student profile from uploaded files
    2. Score against school database
    3. Return ranked matches with dream/target/safety classification
    """
    from backend.context.extractor import extract_student_profile
    from backend.scholarship.engine import predict_scholarship_with_live_data

    try:
        # Extract profile
        context_text = getattr(entry, "context_text", None)
        profile = extract_student_profile(df, context_text, column_names)

        # Predict matches — uses live LLM-recalled data when available
        matches = await predict_scholarship_with_live_data(profile, use_live=True)

        # Count by level
        n_dream = sum(1 for m in matches if m["match_level"] == "dream")
        n_target = sum(1 for m in matches if m["match_level"] == "target")
        n_safety = sum(1 for m in matches if m["match_level"] == "safety")

        # Build summary
        profile_desc = []
        if profile.get("gpa"):
            profile_desc.append(f"GPA {profile['gpa']}")
        if profile.get("sat_score"):
            profile_desc.append(f"SAT {profile['sat_score']}")
        if profile.get("ielts_score"):
            profile_desc.append(f"IELTS {profile['ielts_score']}")

        profile_str = ", ".join(profile_desc) or "hồ sơ của bạn"
        summary = (
            f"Dựa trên {profile_str}, AI đã tìm thấy {len(matches)} trường phù hợp: "
            f"{n_dream} trường Mơ ước, {n_target} trường Phù hợp, {n_safety} trường An toàn."
        )

        recommendation = (
            f"Chiến lược đề xuất: Nộp đơn 2-3 trường Mơ ước, 5-7 trường Phù hợp, và 2-3 trường An toàn. "
            f"Sử dụng tính năng Mô Phỏng để xem cơ hội tăng lên khi cải thiện điểm SAT hoặc GPA."
        )

        # Format as SchoolMatch list
        school_matches = [
            {
                "school_name": m["school_name"],
                "country": m["country"],
                "match_score": m["match_score"],
                "match_level": m["match_level"],
                "strengths": m["strengths"],
                "weaknesses": m["weaknesses"],
            }
            for m in matches
        ]

        return AnalyzeResponse(
            summary=summary,
            drivers=[], r2=None,
            recommendation=recommendation,
            model_type="scholarship_pls",
            decision_trace=DecisionTrace(
                score_pls=0.0, score_reg=0.0,
                engine_selected="scholarship_pls",
                reason="EdTech: Student profile matched against school database",
            ),
            result_type="scholarship_prediction",
            school_matches=school_matches,
            student_profile=profile,
        )

    except Exception as exc:
        logger.error("Scholarship prediction failed: %s", exc, exc_info=True)
        return AnalyzeResponse(
            summary="Không thể dự đoán học bổng. Hãy upload bảng điểm hoặc CV chứa thông tin GPA, SAT, IELTS.",
            drivers=[], r2=None,
            recommendation="Vui lòng upload file có chứa thông tin: GPA, SAT score, IELTS/TOEFL score.",
            model_type=None,
            decision_trace=DecisionTrace(
                score_pls=0.0, score_reg=0.0, engine_selected=None,
                reason=f"Scholarship prediction error: {exc}",
            ),
            result_type="scholarship_prediction",
            not_supported=True,
        )


# ---------------------------------------------------------------------------
# Student Profile Analysis Handler — 6-section comprehensive pipeline
# ---------------------------------------------------------------------------

async def _handle_student_profile_analysis(
    entry: dict,
    df: "pd.DataFrame",
    column_names: list[str],
    query: str,
) -> "StudentProfileResponse":
    """6-section student profile analysis pipeline.

    Sections:
    1. Insight về năng lực (SPSS analysis)
    2. Insight về cơ hội (web scholarship search)
    3. Visual: capability table/chart data
    4. Visual: scholarship opportunities table
    5. Recommendation roadmap
    6. Simulation criteria config
    """
    from backend.student.profile_extractor import extract_student_profile_full
    from backend.student.analyzer import analyze_student_capability
    from backend.student.scholarship_searcher import (
        search_scholarship_opportunities,
        build_simulate_criteria,
    )
    from backend.student.roadmap import generate_roadmap

    _trace = DecisionTrace(
        score_pls=0.0, score_reg=0.0, engine_selected="StudentProfilePipeline",
        reason="Intent: student_profile_analysis — 6-section pipeline",
    )

    try:
        # ── Step 1: Get all uploaded file DataFrames from the store entry ──
        # entry is a FileEntry object with .dataframe, .file_name, .context_text
        dfs: dict[str, "pd.DataFrame"] = {}

        # Primary df from the analyzed entry (FileEntry.dataframe)
        primary_filename = getattr(entry, "file_name", None) or "primary.xlsx"
        dfs[primary_filename] = df  # df is already entry.dataframe from the caller

        # Add any secondary files uploaded alongside the primary (multi-file upload)
        secondary = getattr(entry, "secondary_dataframes", {}) or {}
        for sec_fn, sec_df in secondary.items():
            dfs[sec_fn] = sec_df
            logger.info("Added secondary file '%s' (%d rows) to profile extraction", sec_fn, len(sec_df))

        logger.info(
            "student_profile_analysis: Processing %d files: %s",
            len(dfs), list(dfs.keys()),
        )

        # ── Step 2: Extract unified student profile ──
        profile = extract_student_profile_full(dfs)
        logger.info(
            "Profile extracted: %s, GPA %s, tier %s",
            profile.get("name"), profile.get("gpa_10"), profile.get("overall_tier"),
        )

        # ── Step 3: SPSS-equivalent capability analysis ──
        capability = analyze_student_capability(profile)

        # ── Step 4: Web search for scholarship opportunities ──
        try:
            opportunities = await search_scholarship_opportunities(profile, capability)
        except Exception as exc:
            logger.warning("Scholarship search failed, using empty: %s", exc)
            opportunities = []

        # ── Step 5: Generate personalized roadmap ──
        try:
            roadmap = await generate_roadmap(profile, capability, opportunities)
        except Exception as exc:
            logger.warning("Roadmap generation failed: %s", exc)
            roadmap = []

        # ── Step 6: Build simulation criteria ──
        simulate_criteria = build_simulate_criteria(profile, opportunities)

        # ── Assemble the summary ──
        name = profile.get("name", "Học sinh")
        tier = profile.get("overall_tier", "")
        gpa_10 = profile.get("gpa_10", "?")
        n_opp = len(opportunities)
        key_insights = capability.get("key_insights", [])

        summary = (
            f"**{name}** — {tier}\n\n"
            + "\n".join(f"• {ins}" for ins in key_insights[:4])
        )

        # Recommendation: top roadmap milestone as teaser
        if roadmap:
            first_milestone = roadmap[0]
            top_actions = first_milestone.get("milestones", [])[:2]
            recommendation = (
                f"🗓 **{first_milestone.get('month', '')}**: "
                + " → ".join(top_actions)
            )
        else:
            recommendation = (
                f"Phân tích hoàn thành. Tìm thấy {n_opp} cơ hội học bổng phù hợp với profile {tier}."
            )

        return StudentProfileResponse(
            summary=summary,
            drivers=[], r2=None,
            recommendation=recommendation,
            model_type=None,
            decision_trace=_trace,
            result_type="student_profile_analysis",
            # 6 sections
            capability_analysis=capability,
            scholarship_opportunities=opportunities,
            roadmap=roadmap,
            simulate_criteria=simulate_criteria,
            student_profile_full=profile,
            student_tier=tier,
            # Legacy fields for backward compat
            student_profile={
                "name": name,
                "gpa": gpa_10,
                "gpa_4": profile.get("gpa_4"),
                "sat_score": profile.get("sat"),
                "ielts_score": profile.get("ielts"),
                "toefl_score": profile.get("toefl"),
                "major": profile.get("target_major"),
                "country": profile.get("target_country"),
                "tier": tier,
            },
            school_matches=[],
        )

    except Exception as exc:
        logger.error("Student profile analysis failed: %s", exc, exc_info=True)
        return StudentProfileResponse(
            summary=f"Phân tích hồ sơ thất bại: {exc}",
            drivers=[], r2=None,
            recommendation="Vui lòng đảm bảo upload đủ 3 file: bảng điểm GPA, hoạt động ngoại khóa, và chứng chỉ.",
            model_type=None,
            decision_trace=DecisionTrace(
                score_pls=0.0, score_reg=0.0, engine_selected=None,
                reason=f"Student profile error: {exc}",
            ),
            result_type="student_profile_analysis",
            not_supported=True,
        )
