"""Scholarship improvement simulator.

Computes how a student's scholarship chances change
when they improve specific academic metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.scholarship.engine import _compute_match, _classify_match, _SCHOOL_DB

logger = logging.getLogger(__name__)


def simulate_improvement(
    profile: dict[str, Any],
    school_name: str,
    improvements: dict[str, float],
) -> dict[str, Any]:
    """Simulate the impact of improving academic metrics on scholarship chance.

    Args:
        profile: Current student profile
        school_name: Target school name
        improvements: Dict of {metric: new_value}, e.g. {"sat_score": 1500}

    Returns:
        dict with current_score, new_score, delta, level_change
    """
    # Find school
    school = next((s for s in _SCHOOL_DB if s["name"] == school_name), None)
    if school is None:
        return {
            "type": "simulation",
            "school_name": school_name,
            "current_score": 0,
            "new_score": 0,
            "delta": 0,
            "level_change": None,
        }

    # Current scores
    gpa = profile.get("gpa")
    sat = profile.get("sat_score")
    ielts = profile.get("ielts_score")

    current_score, _, _ = _compute_match(profile, school, gpa, sat, ielts)
    current_level = _classify_match(current_score)

    # Apply improvements
    new_profile = dict(profile)
    new_profile.update(improvements)

    new_gpa = new_profile.get("gpa")
    new_sat = new_profile.get("sat_score")
    new_ielts = new_profile.get("ielts_score")

    new_score, _, _ = _compute_match(new_profile, school, new_gpa, new_sat, new_ielts)
    new_level = _classify_match(new_score)

    delta = new_score - current_score

    # Level change message
    level_change = None
    if new_level != current_level:
        level_labels = {"safety": "An toàn", "target": "Phù hợp", "dream": "Mơ ước"}
        level_change = f"Từ {level_labels.get(current_level, current_level)} → {level_labels.get(new_level, new_level)}"

    return {
        "type": "simulation",
        "school_name": school_name,
        "current_score": current_score,
        "new_score": new_score,
        "delta": delta,
        "level_change": level_change,
    }
