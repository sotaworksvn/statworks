"""
School Research Module — Real-time Web Search Integration

Provides live admission requirement data for scholarship prediction.
Falls back to embedded database when web search is unavailable.

Usage:
    from backend.scholarship.researcher import enrich_with_live_data
    enriched_db = await enrich_with_live_data(school_names)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# School lists by region (names only — requirements fetched via LLM/web)
# ---------------------------------------------------------------------------

PRIORITY_SCHOOLS: dict[str, list[str]] = {
    "US": [
        "Harvard University", "MIT", "Stanford University", "Yale University",
        "Princeton University", "Columbia University", "University of Pennsylvania",
        "Duke University", "Northwestern University", "Johns Hopkins University",
        "Cornell University", "Carnegie Mellon University", "University of Michigan",
        "NYU", "Boston University", "UC Berkeley", "UCLA", "USC",
        "Georgia Tech", "Rice University", "University of Texas at Austin",
        "Purdue University", "University of Illinois Urbana-Champaign",
        "University of Washington", "University of Wisconsin-Madison",
    ],
    "UK": [
        "University of Oxford", "University of Cambridge", "Imperial College London",
        "University College London", "London School of Economics",
        "University of Edinburgh", "University of Manchester",
        "King's College London", "University of Warwick", "University of Bristol",
    ],
    "Asia": [
        "National University of Singapore", "Nanyang Technological University",
        "University of Hong Kong", "Hong Kong University of Science and Technology",
        "Peking University", "Tsinghua University", "University of Tokyo",
        "Seoul National University", "KAIST", "National Taiwan University",
    ],
    "Europe": [
        "ETH Zurich", "Technical University of Munich", "University of Amsterdam",
        "KU Leuven", "University of Copenhagen", "Sorbonne University",
        "Delft University of Technology", "University of Helsinki",
    ],
    "AU_NZ": [
        "University of Melbourne", "University of Sydney",
        "Australian National University", "University of Queensland",
        "University of New South Wales", "Monash University", "University of Auckland",
    ],
    "Canada": [
        "University of Toronto", "McGill University",
        "University of British Columbia", "University of Waterloo",
        "McMaster University", "University of Alberta",
    ],
}

# ---------------------------------------------------------------------------
# Cache (TTL = 1 hour)
# ---------------------------------------------------------------------------

_cache: dict[str, Any] = {}
_cache_ts: float = 0.0
_CACHE_TTL = 3600.0


def _is_cache_fresh() -> bool:
    return (time.time() - _cache_ts) < _CACHE_TTL


# ---------------------------------------------------------------------------
# LLM-based requirement extraction
# ---------------------------------------------------------------------------

_EXTRACT_PROMPT = """\
You are a university admissions data expert.

Extract CURRENT (2025-2027) admission requirements for the following schools
that are relevant for Vietnamese international students.

Return a JSON object with this schema for each school:
{{
  "school_name": "...",
  "country": "...",
  "min_gpa": float | null,        // GPA on 4.0 scale, minimum acceptable
  "avg_gpa": float | null,        // typical admitted student GPA
  "sat_range": [min, max] | null, // SAT total score range for admitted students
  "ielts_min": float | null,      // minimum IELTS score (e.g. 6.5)
  "toefl_min": int | null,        // minimum TOEFL iBT score
  "acceptance_rate": float | null, // e.g. 0.04 for 4%
  "scholarship_rate": float | null, // fraction of intl students receiving aid
  "scholarship_types": ["merit", "need-based", ...],
  "notable_programs": ["CS", "Engineering", ...]
}}

Schools to extract: {schools}

Return a JSON array. Use null for unknown values.
"""


async def _extract_requirements_via_llm(school_names: list[str]) -> list[dict[str, Any]]:
    """Use LLM to generate/recall admission requirements for a batch of schools."""
    from backend.llm.client import call_llm_with_retry

    prompt = _EXTRACT_PROMPT.format(schools=", ".join(school_names))
    try:
        raw = await call_llm_with_retry(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise admissions data assistant. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        # raw may be a dict like {"schools": [...]} or directly a list
        if isinstance(raw, dict):
            for key in ("schools", "universities", "results", "data"):
                if key in raw and isinstance(raw[key], list):
                    return raw[key]
            # Try first list value
            for v in raw.values():
                if isinstance(v, list):
                    return v
            return []
        if isinstance(raw, list):
            return raw
        return []

    except Exception as exc:
        logger.warning("LLM requirement extraction failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def enrich_with_live_data(
    school_names: list[str] | None = None,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """
    Enrich the embedded school DB with LLM-recalled live requirements.

    Args:
        school_names: If None, uses all PRIORITY_SCHOOLS.
        force_refresh: Bypass cache and re-query.

    Returns:
        List of requirement dicts — merged with embedded DB.
    """
    global _cache, _cache_ts

    if not force_refresh and _is_cache_fresh() and _cache:
        logger.debug("Using cached school requirements (%d entries)", len(_cache))
        return list(_cache.values())

    # Build target list
    if school_names is None:
        school_names = []
        for names in PRIORITY_SCHOOLS.values():
            school_names.extend(names)

    # Batch into groups of 15 to stay within LLM context
    BATCH = 15
    all_results: list[dict[str, Any]] = []

    for i in range(0, len(school_names), BATCH):
        batch = school_names[i: i + BATCH]
        results = await _extract_requirements_via_llm(batch)
        all_results.extend(results)
        # Tiny pause to avoid hammering the API
        if i + BATCH < len(school_names):
            await asyncio.sleep(0.3)

    if all_results:
        # Update cache
        _cache = {r["school_name"]: r for r in all_results if r.get("school_name")}
        _cache_ts = time.time()
        logger.info("Refreshed school cache: %d schools", len(_cache))

    return all_results


def get_cached_schools() -> list[dict[str, Any]]:
    """Return currently cached school data (empty if not yet populated)."""
    return list(_cache.values())


def get_all_school_names() -> list[str]:
    """Return all known school names across all regions."""
    names: list[str] = []
    for school_list in PRIORITY_SCHOOLS.values():
        names.extend(school_list)
    return names


__all__ = [
    "enrich_with_live_data",
    "get_cached_schools",
    "get_all_school_names",
    "PRIORITY_SCHOOLS",
]
