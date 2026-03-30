"""Web Search Module — OpenAI Responses API with web_search_preview.

Uses the OpenAI Responses API (not Chat Completions) with the built-in
`web_search_preview` tool for grounded, live, cited answers.

Rule references:
- AI/LLM: openai SDK only (04-rule.md §Python–AI/LLM Layer)
- Security: keys in env vars (04-rule.md §Common–Security)
- Error Handling: 4-layer fallback chain (04-rule.md §Common–Error Handling)
"""

from __future__ import annotations

import logging
from typing import Any

from backend.llm.client import get_active_client

logger = logging.getLogger(__name__)


class WebSearchResult:
    """Result from a web-grounded search query."""

    def __init__(self, answer: str, citations: list[dict[str, str]]) -> None:
        self.answer = answer
        self.citations = citations  # [{"title": ..., "url": ...}]

    def format_with_citations(self) -> str:
        """Return answer + formatted citation list."""
        if not self.citations:
            return self.answer
        lines = [self.answer, "\n\n**Nguồn / Sources:**"]
        for i, c in enumerate(self.citations[:5], 1):
            title = c.get("title", "")
            url = c.get("url", "")
            if url:
                lines.append(f"{i}. [{title}]({url})" if title else f"{i}. {url}")
        return "\n".join(lines)


async def web_search_answer(
    query: str,
    context: str = "",
    max_retries: int = 2,
) -> WebSearchResult | None:
    """Perform a real-time web search using OpenAI Responses API.

    Uses the ``web_search_preview`` built-in tool which is ONLY available
    via the Responses API (``client.responses.create``), NOT via Chat
    Completions.

    Parameters
    ----------
    query : str
        The user's question to answer with live web data.
    context : str
        Optional dataset context to personalize the answer
        (e.g. ``"Student GPA: 7.69/10, IELTS: 6.5"``).
    max_retries : int
        Number of times to retry on transient failure.

    Returns
    -------
    WebSearchResult | None
        ``None`` if the API call fails entirely (caller falls back gracefully).
    """
    client = get_active_client()
    if client is None:
        logger.warning("web_search_answer: No OpenAI client available.")
        return None

    # Build the full prompt that combines web search with user context
    system_instructions = (
        "You are SOTA StatWorks AI — an educational and career planning assistant. "
        "Use ONLY the live web search results to answer this question accurately. "
        "Be specific, cite real universities/programs with actual requirements. "
        "If the user has dataset context (GPA, scores), tailor your answer to their profile. "
        "Respond in the same language as the user's question (Vietnamese or English). "
        "Be concise but complete — no more than 400 words. "
        "Do NOT invent data. If you can't find it via search, say so honestly."
    )

    user_message = query
    if context:
        user_message = f"User context from their data:\n{context}\n\nQuestion: {query}"

    for attempt in range(max_retries + 1):
        try:
            response = await client.responses.create(
                model="gpt-4o-mini",
                tools=[{"type": "web_search_preview"}],
                instructions=system_instructions,
                input=user_message,
            )

            # Extract answer text from response
            answer_text = ""
            citations: list[dict[str, str]] = []

            if hasattr(response, "output"):
                for item in response.output:
                    # Text output
                    if hasattr(item, "type") and item.type == "message":
                        if hasattr(item, "content"):
                            for block in item.content:
                                if hasattr(block, "type") and block.type == "output_text":
                                    answer_text += block.text or ""
                                    # Extract annotations (citations)
                                    if hasattr(block, "annotations"):
                                        for ann in block.annotations:
                                            if hasattr(ann, "type") and ann.type == "url_citation":
                                                citations.append({
                                                    "title": getattr(ann, "title", "") or "",
                                                    "url": getattr(ann, "url", "") or "",
                                                })

            if answer_text:
                logger.info(
                    "web_search_answer: Got %d chars, %d citations",
                    len(answer_text),
                    len(citations),
                )
                return WebSearchResult(answer=answer_text.strip(), citations=citations)

            logger.warning(
                "web_search_answer attempt %d: Empty response", attempt + 1
            )

        except Exception as exc:
            logger.warning(
                "web_search_answer attempt %d failed: %s", attempt + 1, exc
            )
            if attempt < max_retries:
                import asyncio
                await asyncio.sleep(0.5)

    logger.error("web_search_answer: All attempts failed.")
    return None


def _requires_web_search(query: str) -> bool:
    """Heuristic: does this query need live world knowledge (web search)?

    Returns True if the query asks about things outside the dataset —
    university admissions, global rankings, scholarships, tuition fees, etc.
    """
    import unicodedata

    def _norm(text: str) -> str:
        s = unicodedata.normalize("NFD", text)
        s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
        return s.lower()

    q = _norm(query)

    # University / school admission keywords
    universidad_kws = [
        # Vietnamese
        "dai hoc", "truong", "hoc bong", "tuyen sinh", "dieu kien",
        "apply", "nop don", "chuong trinh", "nganh hoc", "master",
        "tren the gioi", "quoc te", "nuoc ngoai", "du hoc",
        "ho tro tai chinh", "hoc phi", "mos",
        # English
        "university", "college", "admission", "scholarship", "requirements",
        "gpa requirement", "ielts requirement", "toefl", "sat", "gre",
        "acceptance rate", "ranking", "worldwide", "international",
        "tuition", "program", "campus", "enroll", "application",
    ]
    return any(kw in q for kw in universidad_kws)


__all__ = ["web_search_answer", "_requires_web_search", "WebSearchResult"]
