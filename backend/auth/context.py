"""Clerk identity extraction — header-only, no Clerk SDK on backend.

Per ADR-0001 and Rule §Auth:
  • Extract ``clerk_user_id`` from the ``x-clerk-user-id`` request header.
  • Return ``None`` for anonymous (unauthenticated) requests.
  • Never import or depend on any Clerk backend SDK.
"""

from __future__ import annotations

from fastapi import Request


def get_current_user_id(request: Request) -> str | None:
    """Extract the Clerk user ID from request headers.

    Returns
    -------
    str | None
        The ``clerk_user_id`` if the header is present, otherwise ``None``
        (anonymous request).
    """
    return request.headers.get("x-clerk-user-id") or None
