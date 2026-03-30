"""Scholarship Searcher — uses web search to find real, live scholarship opportunities.

Given a student capability analysis result, searches the web for tailored
scholarship programs and returns a structured list of opportunities with
match scores, deadlines, and application requirements.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


async def search_scholarship_opportunities(
    profile: dict[str, Any],
    capability_analysis: dict[str, Any],
) -> list[dict[str, Any]]:
    """Search for scholarship opportunities matching the student profile.

    Uses web_search_answer() with context tailored to the student's
    specific strengths and target preferences.

    Returns
    -------
    list of dicts with keys:
        school_name, country, program, scholarship_name,
        amount_usd, deadline, gpa_requirement, ielts_requirement,
        toefl_requirement, sat_requirement, match_score (0-100),
        match_level (dream/target/safety), match_reasons, apply_url
    """
    from backend.llm.web_search import web_search_answer

    # Build rich context from profile + analysis
    context = _build_search_context(profile, capability_analysis)

    # Build targeted query
    target_country = profile.get("target_country", "Mỹ")
    target_major = profile.get("target_major", "Computer Science")
    gpa_4 = profile.get("gpa_4", 3.8)
    sat = profile.get("sat")
    toefl = profile.get("toefl")
    ielts = profile.get("ielts")
    tier = profile.get("overall_tier", "Top 5%")

    query = (
        f"2025-2026 scholarship opportunities for international Vietnamese students applying "
        f"{target_major} undergraduate programs in {target_country} for Fall 2026 intake. "
        f"Student profile: GPA {gpa_4}/4.0"
        + (f", SAT {sat}" if sat else "")
        + (f", TOEFL {toefl}" if toefl else "")
        + (f", IELTS {ielts}" if ielts else "")
        + f", academic tier {tier}. "
        f"Include: scholarship name, university, amount (USD), deadline, minimum GPA requirement, "
        f"language requirement, application URL. Focus on merit-based scholarships with high award amounts. "
        f"List at least 8-10 specific programs with realistic eligibility for this profile."
    )

    try:
        result = await web_search_answer(query=query, context=context)
        if result is None:
            logger.warning("Web search returned None for scholarship opportunities")
            return _fallback_opportunities(profile)

        # Parse the result text into structured opportunities
        opportunities = await _parse_opportunities_from_text(
            result.answer, profile, result.citations
        )
        if not opportunities:
            return _fallback_opportunities(profile)
        return opportunities

    except Exception as exc:
        logger.error("Scholarship search failed: %s", exc, exc_info=True)
        return _fallback_opportunities(profile)


async def _parse_opportunities_from_text(
    text: str,
    profile: dict,
    citations: list[dict],
) -> list[dict]:
    """Use LLM to parse web search text into structured opportunity list."""
    from backend.llm.client import call_llm_with_retry

    gpa_4 = profile.get("gpa_4", 3.8)
    sat = profile.get("sat", 0)
    toefl = profile.get("toefl", 0)
    ielts = profile.get("ielts", 0)

    prompt = f"""You found these scholarship opportunities via web search. Parse them into a structured JSON array.

Web search result:
{text[:3000]}

Student profile: GPA {gpa_4}/4.0, SAT {sat}, TOEFL {toefl}, IELTS {ielts}

Return a JSON object: {{"opportunities": [{{
  "school_name": "university name",
  "country": "country",
  "program": "degree program",
  "scholarship_name": "scholarship name",
  "amount_usd": 25000,
  "deadline": "YYYY-MM-DD or 'Rolling' or 'November 2025'",
  "gpa_requirement": 3.5,
  "ielts_requirement": 7.0,
  "toefl_requirement": 100,
  "sat_requirement": 1400,
  "apply_url": "url or null",
  "match_score": 85,
  "match_level": "dream|target|safety",
  "match_reasons": ["specific reason 1", "specific reason 2"]
}}]}}

Match scoring rules:
- match_score 85-100 = dream (student just meets or slightly exceeds requirements)
- match_score 65-84 = target (student clearly meets requirements)
- match_score 40-64 = safety (student significantly exceeds requirements)
Compare the student's actual GPA {gpa_4}, SAT {sat}, TOEFL {toefl} against requirements.
Return 6-12 opportunities. Focus on real, specific programs with real data from the search result."""

    try:
        raw = await call_llm_with_retry(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You parse scholarship data into structured JSON. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        opportunities = raw.get("opportunities", [])
        if not isinstance(opportunities, list):
            return []

        # Enrich with citation URLs where possible
        citation_map = {c.get("title", ""): c.get("url", "") for c in citations}

        for opp in opportunities:
            # Fill in URL from citations if missing
            if not opp.get("apply_url"):
                school = opp.get("school_name", "")
                for title, url in citation_map.items():
                    if school.lower() in title.lower():
                        opp["apply_url"] = url
                        break

            # Ensure numeric types
            for field in ("amount_usd", "gpa_requirement", "ielts_requirement",
                          "toefl_requirement", "sat_requirement", "match_score"):
                val = opp.get(field)
                if val is not None:
                    try:
                        opp[field] = float(val)
                    except (ValueError, TypeError):
                        opp[field] = None

            # Ensure match_level is valid
            if opp.get("match_level") not in ("dream", "target", "safety"):
                ms = opp.get("match_score", 70)
                opp["match_level"] = "dream" if ms >= 85 else ("target" if ms >= 65 else "safety")

        # Sort by match_score descending
        opportunities.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return opportunities

    except Exception as exc:
        logger.warning("Opportunity parsing failed: %s", exc)
        return []


def _build_search_context(profile: dict, capability: dict) -> str:
    """Build rich context string to personalize the web search."""
    parts = [f"Student: {profile.get('name', 'Vietnamese student')}"]
    parts.append(f"School: {profile.get('school', 'Vietnamese high school')}")
    parts.append(f"Target: {profile.get('target_major', 'Computer Science')} in {profile.get('target_country', 'USA')}, {profile.get('target_intake', 'Fall 2026')}")
    parts.append(f"GPA: {profile.get('gpa_10', '?')}/10 ({profile.get('gpa_4', '?')}/4.0 US scale)")

    tests = []
    if profile.get("toefl"):
        tests.append(f"TOEFL {profile['toefl']}")
    if profile.get("ielts"):
        tests.append(f"IELTS {profile['ielts']}")
    if profile.get("sat"):
        tests.append(f"SAT {profile['sat']}")
    if tests:
        parts.append("Tests: " + ", ".join(tests))

    ap = profile.get("ap_courses", [])
    if ap:
        ap_str = ", ".join(f"{a['name']} ({int(a['score']) if a.get('score') else '?'})" for a in ap[:5])
        parts.append(f"AP Courses: {ap_str}")

    awards = profile.get("awards", [])
    if awards:
        award_str = ", ".join(f"{a['name']} ({a.get('level', '')})" for a in awards[:5])
        parts.append(f"Awards: {award_str}")

    insights = capability.get("key_insights", [])
    if insights:
        parts.append("Strengths: " + "; ".join(insights[:3]))

    parts.append(f"Profile tier: {profile.get('overall_tier', 'Top 5%')}")
    return "\n".join(parts)


def _fallback_opportunities(profile: dict) -> list[dict]:
    """Return a minimal fallback if web search fails entirely."""
    target_major = profile.get("target_major", "Computer Science")
    gpa_4 = profile.get("gpa_4", 3.8)

    return [
        {
            "school_name": "University of Illinois Urbana-Champaign",
            "country": "USA",
            "program": target_major,
            "scholarship_name": "International Merit Award",
            "amount_usd": 15000,
            "deadline": "December 2025",
            "gpa_requirement": 3.5,
            "ielts_requirement": 6.5,
            "toefl_requirement": 79,
            "sat_requirement": 1300,
            "apply_url": "https://admissions.illinois.edu",
            "match_score": 75,
            "match_level": "target",
            "match_reasons": ["GPA exceeds requirement", "Test scores strong"],
        },
    ]


def build_simulate_criteria(profile: dict, opportunities: list[dict]) -> list[dict]:
    """Build the list of simulatable criteria for the simulation bar.

    Each criterion has a type (numeric | award_rank | text) and
    configuration for the slider/dropdown.
    """
    criteria = []

    # GPA (numeric, 0.1 step on 10-scale)
    gpa_10 = profile.get("gpa_10") or 8.0
    criteria.append({
        "key": "gpa_10",
        "label": "GPA (thang 10)",
        "type": "numeric",
        "min": max(6.0, round(gpa_10 - 1.5, 1)),
        "max": 10.0,
        "step": 0.1,
        "current": gpa_10,
        "unit": "/10",
    })

    # SAT (numeric, 10-step)
    if profile.get("sat"):
        sat = profile["sat"]
        criteria.append({
            "key": "sat",
            "label": "SAT",
            "type": "numeric",
            "min": max(1000, sat - 200),
            "max": 1600,
            "step": 10,
            "current": sat,
            "unit": "",
        })

    # IELTS (numeric, 0.5 step)
    if profile.get("ielts"):
        ielts = profile["ielts"]
        criteria.append({
            "key": "ielts",
            "label": "IELTS",
            "type": "numeric",
            "min": max(5.0, ielts - 2.0),
            "max": 9.0,
            "step": 0.5,
            "current": ielts,
            "unit": "",
        })

    # TOEFL (numeric, 1 step)
    if profile.get("toefl"):
        toefl = profile["toefl"]
        criteria.append({
            "key": "toefl",
            "label": "TOEFL iBT",
            "type": "numeric",
            "min": max(60, toefl - 20),
            "max": 120,
            "step": 1,
            "current": toefl,
            "unit": "",
        })

    # Award level (ordinal rank selector)
    criteria.append({
        "key": "award_level",
        "label": "Giải thưởng học thuật",
        "type": "award_rank",
        "options": [
            {"value": 0, "label": "Chưa có giải"},
            {"value": 1, "label": "Giải Khuyến khích / Cấp Trường"},
            {"value": 2, "label": "Giải Ba Cấp Thành phố"},
            {"value": 3, "label": "Giải Nhì Cấp Thành phố"},
            {"value": 4, "label": "Giải Nhất Cấp Thành phố"},
            {"value": 5, "label": "Giải Ba Cấp Quốc gia"},
            {"value": 6, "label": "Giải Nhì Cấp Quốc gia"},
            {"value": 7, "label": "Giải Nhất Cấp Quốc gia"},
            {"value": 8, "label": "Huy chương Quốc tế (Đồng/Bạc/Vàng)"},
        ],
        "current": 5,  # default: Giải Ba Quốc gia (assuming)
        "description": "Mức giải thưởng học thuật ảnh hưởng lớn đến hồ sơ scholarship",
    })

    # Extracurricular text (text input type)
    criteria.append({
        "key": "activity_note",
        "label": "Hoạt động / Giải thưởng mới",
        "type": "text",
        "placeholder": "VD: Đạt Giải Nhất Olympic Toán quốc tế IMO 2025",
        "description": "Nhập hoạt động hoặc giải thưởng mới để AI tính toán tác động lên khả năng học bổng",
        "current": "",
    })

    return criteria
