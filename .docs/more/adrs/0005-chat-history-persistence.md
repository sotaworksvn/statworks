# ADR-0005: Chat History Persistence via Supabase

**Status:** proposed
**Date:** 2026-03-21
**Last updated:** 2026-03-21

**Chose:** Supabase PostgreSQL (conversations + messages + conversation_files tables) over client-side localStorage, over Redis/dedicated chat service

**Rationale:** Supabase PostgreSQL is already used for user records and dataset metadata (ADR-0002). Adding three tables for conversation persistence reuses existing infrastructure with zero additional cost. JSONB content column supports both plain-text user queries and structured InsightResult JSON from the AI. Free tier (500MB) can store ~500K messages — more than sufficient for MVP/demo.

## Alternatives Considered

- **Client-side localStorage**: Simple but non-persistent across devices/sessions, limited storage (~5MB), and violates the requirement that conversations survive re-login.
- **Redis**: Fast but adds infrastructure complexity and cost. Chat history is read-heavy with infrequent writes — PostgreSQL handles this well. Redis is appropriate if sub-millisecond access is needed, which it is not.
- **Dedicated chat service (e.g., Stream, Ably)**: Over-engineered for the use case. Adds external dependency, cost, and complexity. The app does not need real-time multi-user chat.

## Consequences

- **Schema changes:** Three new Supabase tables (`conversations`, `messages`, `conversation_files`). One-time migration.
- **API surface expansion:** Four new endpoints on the FastAPI backend. Well-scoped CRUD operations.
- **Message saving is async:** To avoid delaying insight delivery, message persistence happens in background (fire-and-forget with error logging).
- **No conversation search in v1:** Conversations are listed chronologically. Full-text search can be added later via PostgreSQL `tsvector`.
