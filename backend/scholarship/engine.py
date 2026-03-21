"""Scholarship prediction engine.

Uses PLS-based scoring or heuristic matching to predict
scholarship chances at multiple schools.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


# ─── School database (embedded, no external API needed) ───────────────────────

# Sample school requirements — in production this would be a DB/API
_SCHOOL_DB: list[dict[str, Any]] = [
    # Top US Universities
    {"name": "Harvard University", "country": "USA", "min_gpa": 3.9, "avg_sat": 1540, "avg_ielts": 8.0, "scholarship_rate": 0.70},
    {"name": "MIT", "country": "USA", "min_gpa": 3.9, "avg_sat": 1545, "avg_ielts": 7.5, "scholarship_rate": 0.65},
    {"name": "Stanford University", "country": "USA", "min_gpa": 3.85, "avg_sat": 1535, "avg_ielts": 7.5, "scholarship_rate": 0.60},
    {"name": "Yale University", "country": "USA", "min_gpa": 3.85, "avg_sat": 1530, "avg_ielts": 7.5, "scholarship_rate": 0.65},
    {"name": "Columbia University", "country": "USA", "min_gpa": 3.8, "avg_sat": 1520, "avg_ielts": 7.0, "scholarship_rate": 0.55},
    {"name": "University of Pennsylvania", "country": "USA", "min_gpa": 3.8, "avg_sat": 1515, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    {"name": "Duke University", "country": "USA", "min_gpa": 3.75, "avg_sat": 1510, "avg_ielts": 7.0, "scholarship_rate": 0.55},
    {"name": "University of Chicago", "country": "USA", "min_gpa": 3.75, "avg_sat": 1510, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    {"name": "Northwestern University", "country": "USA", "min_gpa": 3.75, "avg_sat": 1500, "avg_ielts": 7.0, "scholarship_rate": 0.45},
    {"name": "Johns Hopkins University", "country": "USA", "min_gpa": 3.7, "avg_sat": 1500, "avg_ielts": 7.0, "scholarship_rate": 0.55},
    {"name": "Cornell University", "country": "USA", "min_gpa": 3.7, "avg_sat": 1490, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    {"name": "Dartmouth College", "country": "USA", "min_gpa": 3.7, "avg_sat": 1490, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    {"name": "Brown University", "country": "USA", "min_gpa": 3.7, "avg_sat": 1490, "avg_ielts": 7.0, "scholarship_rate": 0.45},
    {"name": "Vanderbilt University", "country": "USA", "min_gpa": 3.65, "avg_sat": 1490, "avg_ielts": 7.0, "scholarship_rate": 0.65},
    {"name": "Carnegie Mellon University", "country": "USA", "min_gpa": 3.65, "avg_sat": 1490, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    {"name": "University of Michigan", "country": "USA", "min_gpa": 3.6, "avg_sat": 1460, "avg_ielts": 6.5, "scholarship_rate": 0.45},
    {"name": "NYU", "country": "USA", "min_gpa": 3.5, "avg_sat": 1400, "avg_ielts": 6.5, "scholarship_rate": 0.40},
    {"name": "Boston University", "country": "USA", "min_gpa": 3.4, "avg_sat": 1380, "avg_ielts": 6.5, "scholarship_rate": 0.60},
    {"name": "University of California, Berkeley", "country": "USA", "min_gpa": 3.7, "avg_sat": 1470, "avg_ielts": 6.5, "scholarship_rate": 0.35},
    {"name": "UCLA", "country": "USA", "min_gpa": 3.65, "avg_sat": 1440, "avg_ielts": 6.5, "scholarship_rate": 0.30},
    # UK Universities
    {"name": "University of Oxford", "country": "UK", "min_gpa": 3.85, "avg_sat": None, "avg_ielts": 7.5, "scholarship_rate": 0.40},
    {"name": "University of Cambridge", "country": "UK", "min_gpa": 3.85, "avg_sat": None, "avg_ielts": 7.5, "scholarship_rate": 0.40},
    {"name": "Imperial College London", "country": "UK", "min_gpa": 3.7, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.45},
    {"name": "UCL", "country": "UK", "min_gpa": 3.6, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    {"name": "LSE", "country": "UK", "min_gpa": 3.6, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.45},
    {"name": "University of Edinburgh", "country": "UK", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    {"name": "University of Manchester", "country": "UK", "min_gpa": 3.4, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.60},
    {"name": "University of Bristol", "country": "UK", "min_gpa": 3.4, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    # Australian Universities
    {"name": "University of Melbourne", "country": "Australia", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.55},
    {"name": "Australian National University", "country": "Australia", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.60},
    {"name": "University of Sydney", "country": "Australia", "min_gpa": 3.4, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.50},
    {"name": "UNSW", "country": "Australia", "min_gpa": 3.4, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.50},
    {"name": "Monash University", "country": "Australia", "min_gpa": 3.2, "avg_sat": None, "avg_ielts": 6.0, "scholarship_rate": 0.55},
    # Canadian Universities
    {"name": "University of Toronto", "country": "Canada", "min_gpa": 3.7, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    {"name": "McGill University", "country": "Canada", "min_gpa": 3.6, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    {"name": "UBC", "country": "Canada", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.50},
    {"name": "University of Waterloo", "country": "Canada", "min_gpa": 3.4, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.60},
    # Singapore/Asian Universities
    {"name": "NUS (National University of Singapore)", "country": "Singapore", "min_gpa": 3.6, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.65},
    {"name": "NTU Singapore", "country": "Singapore", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.65},
    {"name": "HKUST", "country": "Hong Kong", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.60},
    {"name": "HKU", "country": "Hong Kong", "min_gpa": 3.4, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    # European Universities
    {"name": "ETH Zurich", "country": "Switzerland", "min_gpa": 3.8, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.45},
    {"name": "TU Munich", "country": "Germany", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    {"name": "KU Leuven", "country": "Belgium", "min_gpa": 3.4, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    {"name": "Maastricht University", "country": "Netherlands", "min_gpa": 3.2, "avg_sat": None, "avg_ielts": 6.0, "scholarship_rate": 0.60},
    {"name": "Delft University of Technology", "country": "Netherlands", "min_gpa": 3.3, "avg_sat": None, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    {"name": "Sciences Po Paris", "country": "France", "min_gpa": 3.5, "avg_sat": None, "avg_ielts": 7.0, "scholarship_rate": 0.50},
    # More US mid-tier
    {"name": "Purdue University", "country": "USA", "min_gpa": 3.4, "avg_sat": 1380, "avg_ielts": 6.5, "scholarship_rate": 0.55},
    {"name": "University of Wisconsin-Madison", "country": "USA", "min_gpa": 3.4, "avg_sat": 1390, "avg_ielts": 6.5, "scholarship_rate": 0.50},
    {"name": "Penn State", "country": "USA", "min_gpa": 3.3, "avg_sat": 1290, "avg_ielts": 6.0, "scholarship_rate": 0.55},
    {"name": "Indiana University Bloomington", "country": "USA", "min_gpa": 3.2, "avg_sat": 1250, "avg_ielts": 6.0, "scholarship_rate": 0.65},
    {"name": "Arizona State University", "country": "USA", "min_gpa": 3.0, "avg_sat": 1220, "avg_ielts": 6.0, "scholarship_rate": 0.70},
]


def predict_scholarship(profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Score all schools against the student profile.

    Returns a list of school match dicts sorted by match_score descending.
    """
    gpa = profile.get("gpa")
    sat = profile.get("sat_score")
    ielts = profile.get("ielts_score")
    toefl = profile.get("toefl_score")

    # Convert TOEFL → IELTS equivalent for unified scoring
    if ielts is None and toefl is not None:
        ielts = _toefl_to_ielts(toefl)

    results = []
    for school in _SCHOOL_DB:
        score, strengths, weaknesses = _compute_match(profile, school, gpa, sat, ielts)
        if score < 5:  # skip extremely low matches
            continue

        match_level = _classify_match(score)
        results.append({
            "school_name": school["name"],
            "country": school["country"],
            "match_score": score,
            "match_level": match_level,
            "strengths": strengths,
            "weaknesses": weaknesses,
        })

    # Sort by score descending
    results.sort(key=lambda x: x["match_score"], reverse=True)

    # Return top 30 (mix of dream/target/safety)
    return _balanced_selection(results, max_total=30)


def _compute_match(
    profile: dict[str, Any],
    school: dict[str, Any],
    gpa: float | None,
    sat: int | None,
    ielts: float | None,
) -> tuple[int, list[str], list[str]]:
    """Compute a 0-100 match score for one school."""
    total_weight = 0.0
    weighted_score = 0.0
    strengths = []
    weaknesses = []

    # ── GPA (weight: 40%) ──
    if gpa is not None:
        min_gpa = school["min_gpa"]
        gpa_score = _score_metric(gpa, min_gpa, min_gpa * 0.85, min_gpa * 1.05)
        weighted_score += 40 * gpa_score
        total_weight += 40
        if gpa_score >= 0.8:
            strengths.append(f"GPA {gpa:.2f} mạnh")
        elif gpa_score < 0.5:
            weaknesses.append(f"GPA {gpa:.2f} < yêu cầu {min_gpa}")

    # ── SAT (weight: 25% if available) ──
    if sat is not None and school["avg_sat"] is not None:
        avg_sat = school["avg_sat"]
        sat_score = _score_metric(sat, avg_sat * 0.95, avg_sat * 0.80, avg_sat * 1.05)
        weighted_score += 25 * sat_score
        total_weight += 25
        if sat_score >= 0.8:
            strengths.append(f"SAT {sat} vượt mức")
        elif sat_score < 0.5:
            weaknesses.append(f"SAT {sat} thấp hơn mức trung bình {avg_sat}")

    # ── IELTS (weight: 20%) ──
    if ielts is not None:
        avg_ielts = school["avg_ielts"]
        ielts_score_val = _score_metric(ielts, avg_ielts * 0.95, avg_ielts * 0.80, avg_ielts * 1.05)
        weighted_score += 20 * ielts_score_val
        total_weight += 20
        if ielts_score_val >= 0.8:
            strengths.append(f"IELTS {ielts} đạt yêu cầu")
        elif ielts_score_val < 0.5:
            weaknesses.append(f"IELTS {ielts} cần cải thiện (yêu cầu {avg_ielts})")

    # ── Scholarship bonus (weight: 15%) ──
    scholarship_rate = school.get("scholarship_rate", 0.5)
    scholarship_component = scholarship_rate  # 0-1
    weighted_score += 15 * scholarship_component
    total_weight += 15

    if total_weight == 0:
        return 0, [], []

    raw_score = weighted_score / total_weight
    final_score = int(round(raw_score * 100))
    final_score = max(0, min(99, final_score))

    return final_score, strengths[:3], weaknesses[:2]


def _score_metric(value: float, target: float, floor: float, ceiling: float) -> float:
    """Map a metric value to a 0.0-1.0 score using sigmoid-like scaling."""
    if value >= ceiling:
        return 1.0
    if value <= floor:
        return 0.1
    # Linear interpolation between floor and ceiling
    return 0.1 + 0.9 * (value - floor) / (ceiling - floor)


def _classify_match(score: int) -> str:
    """Classify school by match score."""
    if score >= 70:
        return "dream"
    if score >= 45:
        return "target"
    return "safety"


def _toefl_to_ielts(toefl: int) -> float:
    """Approximate TOEFL iBT → IELTS band conversion."""
    conversion = {
        118: 9.0, 115: 8.5, 110: 8.0, 102: 7.5, 94: 7.0,
        79: 6.5, 60: 6.0, 46: 5.5, 35: 5.0,
    }
    for t_score, i_band in sorted(conversion.items(), reverse=True):
        if toefl >= t_score:
            return i_band
    return 4.5


def _balanced_selection(
    results: list[dict[str, Any]],
    max_total: int = 30,
) -> list[dict[str, Any]]:
    """Return a balanced mix of dream/target/safety schools."""
    dream = [r for r in results if r["match_level"] == "dream"]
    target = [r for r in results if r["match_level"] == "target"]
    safety = [r for r in results if r["match_level"] == "safety"]

    selected = (
        dream[:8]   # top 8 dreams
        + target[:14]  # top 14 targets
        + safety[:8]   # top 8 safeties
    )

    # Sort by score descending for display
    selected.sort(key=lambda x: x["match_score"], reverse=True)
    return selected[:max_total]
