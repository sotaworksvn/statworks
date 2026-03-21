"""LLM Call 2 — Insight generation via gpt-5.4 (Phase 2 · task 2.3).

Rule references:
- AI/LLM: gpt-5.4 for Call 2 only (04-rule.md §Python–AI/LLM Layer)
- UX: no jargon (04-rule.md §React/Next.js–UX)
- Error Handling: Layer 4 fallback (04-rule.md §Common–Error Handling)
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel

from backend.llm.client import LLMFailureError, call_llm_with_retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class InsightText(BaseModel):
    """Structured insight returned by LLM Call 2 (or template fallback)."""

    summary: str
    recommendation: str


# ---------------------------------------------------------------------------
# System prompt — business language, no jargon
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_INSIGHT: str = (
    "You are a business insights advisor. Given statistical analysis results, "
    "write a concise summary and one actionable recommendation in plain "
    "business language.\n\n"
    "CRITICAL RULES:\n"
    "- Do NOT use these words: coefficient, p-value, regression, PLS, OLS, "
    "bootstrap, latent variable, SEM, beta, R-squared.\n"
    "- Write as if advising a CEO who has never taken a statistics class.\n"
    "- The summary should be 1-2 sentences explaining the key finding.\n"
    "- The recommendation should be 1-2 sentences of actionable advice.\n"
    "- The drivers are listed in order from STRONGEST to WEAKEST impact. "
    "Your summary MUST reflect this same ranking order — mention the #1 "
    "driver first, then secondary drivers.\n\n"
    "Return ONLY valid JSON matching this schema:\n"
    '{"summary": "string", "recommendation": "string"}\n'
    "Do not include markdown, code fences, or explanation."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def generate_insight(
    drivers: list[dict],
    r2: float | None,
    target: str,
    model_type: str,
    user_query: str = "",
) -> InsightText:
    """Generate business-language insight using gpt-5.4.

    Parameters
    ----------
    drivers : list[dict]
        List of driver dicts with ``name``, ``coef``, ``p_value``, ``significant``.
        Pre-sorted by absolute impact (strongest first).
    r2 : float | None
        R-squared value from the model.
    target : str
        The target variable name.
    model_type : str
        ``"regression"`` or ``"pls"``.

    Returns
    -------
    InsightText
        Summary and recommendation text.
        On LLM failure, returns template-generated strings (Layer 4 fallback).
    """

    # Build a natural-language summary of results for the LLM prompt
    if not drivers:
        return _template_fallback(drivers, target)

    driver_lines: list[str] = []
    for rank, d in enumerate(drivers[:5], start=1):
        direction = "positively" if d["coef"] > 0 else "negatively"
        strength = abs(d["coef"])
        sig_label = "strong" if d.get("significant", False) else "weak"
        driver_lines.append(
            f"- #{rank} {d['name']} has a {sig_label} {direction} relationship "
            f"with {target} (impact strength: {strength:.2f})"
        )

    fit_desc = ""
    if r2 is not None:
        pct = r2 * 100
        if pct > 60:
            fit_desc = f"The model explains {pct:.0f}% of the variation, which is a strong fit."
        elif pct > 30:
            fit_desc = f"The model explains {pct:.0f}% of the variation, a moderate fit."
        else:
            fit_desc = f"The model explains {pct:.0f}% of the variation, suggesting other factors are also at play."

    user_prompt = (
        f"User's original question: {user_query}\n\n" if user_query else ""
    ) + (
        f"Target outcome: {target}\n"
        f"Key findings (ranked by impact, strongest first):\n"
        + "\n".join(driver_lines)
        + ("\n" + fit_desc if fit_desc else "")
        + "\n\nPlease provide a summary and recommendation that directly answer the user's question."
    )

    try:
        result = await call_llm_with_retry(
            model="gpt-5.4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_INSIGHT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        if isinstance(result, dict) and "summary" in result and "recommendation" in result:
            return InsightText(
                summary=result["summary"],
                recommendation=result["recommendation"],
            )

        logger.warning("LLM Call 2 returned unexpected shape: %s", result)
        return _template_fallback(drivers, target)

    except LLMFailureError as exc:
        logger.warning("LLM Call 2 failed, using template fallback: %s", exc)
        return _template_fallback(drivers, target)


def _template_fallback(
    drivers: list[dict],
    target: str,
) -> InsightText:
    """Layer 4 fallback — template-generated insight strings."""

    if drivers:
        top = drivers[0]
        summary = (
            f"{top['name']} shows the strongest relationship with "
            f"{target} (impact score {abs(top['coef']):.2f})."
        )
        recommendation = (
            f"Focus on improving {top['name']} to drive better "
            f"{target} outcomes."
        )
    else:
        summary = "No strong drivers identified."
        recommendation = "Try a different question or check your dataset."

    return InsightText(summary=summary, recommendation=recommendation)
