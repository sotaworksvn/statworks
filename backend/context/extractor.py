"""Student profile extractor from uploaded files.

Extracts GPA, SAT, IELTS, TOEFL, major, grade level etc.
from context_text (Word/PowerPoint) or structured CSV/Excel data.
"""

from __future__ import annotations

import re
import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def extract_student_profile(
    df: pd.DataFrame | None,
    context_text: str | None,
    column_names: list[str],
) -> dict[str, Any]:
    """Extract a student profile dictionary from all available data sources.

    Priority: context_text (CV/transcript) > dataframe columns > defaults.

    Returns:
        dict with keys: gpa, sat_score, ielts_score, toefl_score,
                        major, grade_level, activities, awards
    """
    profile: dict[str, Any] = {
        "gpa": None,
        "sat_score": None,
        "ielts_score": None,
        "toefl_score": None,
        "major": None,
        "grade_level": None,
        "activities": [],
        "awards": [],
    }

    # ── 1. Parse from context_text (CV, transcript, cover letter) ──────────
    if context_text:
        profile.update(_extract_from_text(context_text))

    # ── 2. Fill from DataFrame columns ─────────────────────────────────────
    if df is not None and not df.empty:
        lower_cols = {c.lower(): c for c in df.columns}

        # GPA
        if profile["gpa"] is None:
            for key in ("gpa", "grade_point_average", "điểm_gpa", "diem_gpa"):
                if key in lower_cols:
                    val = _first_numeric(df[lower_cols[key]])
                    if val is not None:
                        profile["gpa"] = round(float(val), 2)
                        break

        # SAT
        if profile["sat_score"] is None:
            for key in ("sat", "sat_score", "sat_total"):
                if key in lower_cols:
                    val = _first_numeric(df[lower_cols[key]])
                    if val is not None:
                        profile["sat_score"] = int(val)
                        break

        # IELTS
        if profile["ielts_score"] is None:
            for key in ("ielts", "ielts_score", "ielts_band"):
                if key in lower_cols:
                    val = _first_numeric(df[lower_cols[key]])
                    if val is not None:
                        profile["ielts_score"] = round(float(val), 1)
                        break

        # TOEFL
        if profile["toefl_score"] is None:
            for key in ("toefl", "toefl_score", "toefl_ibt"):
                if key in lower_cols:
                    val = _first_numeric(df[lower_cols[key]])
                    if val is not None:
                        profile["toefl_score"] = int(val)
                        break

        # Major
        if profile["major"] is None:
            for key in ("major", "ngành", "nganh", "field_of_study"):
                if key in lower_cols:
                    val = df[lower_cols[key]].dropna().iloc[0] if not df[lower_cols[key]].dropna().empty else None
                    if val is not None:
                        profile["major"] = str(val)
                        break

    return profile


def _extract_from_text(text: str) -> dict[str, Any]:
    """Use regex patterns to extract academic metrics from free text."""
    result: dict[str, Any] = {}

    # GPA patterns: "GPA: 3.8", "GPA 3.80/4.0", "điểm GPA 3.7"
    gpa_match = re.search(
        r"(?:gpa|grade point average|điểm gpa)[:\s]+(\d+[.,]\d{1,2})(?:\s*/\s*4(?:\.0)?)?",
        text, re.IGNORECASE
    )
    if gpa_match:
        try:
            result["gpa"] = round(float(gpa_match.group(1).replace(",", ".")), 2)
        except ValueError:
            pass

    # SAT patterns: "SAT: 1450", "SAT Score: 1500"
    sat_match = re.search(
        r"(?:sat(?:\s+(?:score|total|composite))?)[:\s]+(\d{3,4})",
        text, re.IGNORECASE
    )
    if sat_match:
        try:
            result["sat_score"] = int(sat_match.group(1))
        except ValueError:
            pass

    # IELTS patterns: "IELTS: 7.5", "IELTS Overall 8.0"
    ielts_match = re.search(
        r"(?:ielts(?:\s+(?:score|overall|band))?)[:\s]+(\d+[.,]\d?)",
        text, re.IGNORECASE
    )
    if ielts_match:
        try:
            result["ielts_score"] = round(float(ielts_match.group(1).replace(",", ".")), 1)
        except ValueError:
            pass

    # TOEFL patterns: "TOEFL: 110", "TOEFL iBT 105"
    toefl_match = re.search(
        r"(?:toefl(?:\s+(?:ibt|score|total))?)[:\s]+(\d{2,3})",
        text, re.IGNORECASE
    )
    if toefl_match:
        try:
            result["toefl_score"] = int(toefl_match.group(1))
        except ValueError:
            pass

    # Major / field of study
    major_match = re.search(
        r"(?:major|ngành học|field of study|studying)[:\s]+([A-Za-zÀ-ỹ\s&,/]+?)(?:\n|;|\.|$)",
        text, re.IGNORECASE
    )
    if major_match:
        major_text = major_match.group(1).strip()
        if 2 < len(major_text) < 80:
            result["major"] = major_text

    # Activities (simple extraction)
    activities = re.findall(
        r"(?:club|team|volunteer|internship|competition|award|prize|scholarship)[:\s]+([^\n;.]+)",
        text, re.IGNORECASE
    )
    if activities:
        result["activities"] = [a.strip() for a in activities[:5]]

    return result


def _first_numeric(series: pd.Series) -> float | None:
    """Return the first non-null numeric value from a series."""
    try:
        cleaned = pd.to_numeric(series, errors="coerce").dropna()
        if not cleaned.empty:
            return float(cleaned.iloc[0])
    except Exception:
        pass
    return None
