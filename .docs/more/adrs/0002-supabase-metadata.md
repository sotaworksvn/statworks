# ADR-0002: Supabase for Metadata Persistence

**Status:** proposed
**Date:** 2026-03-20
**Last updated:** 2026-03-20

**Chose:** Supabase (PostgreSQL) over SQLite, Firebase Firestore, PlanetScale
**Rationale:** Supabase provides a managed PostgreSQL instance with a generous free tier (500 MB database, 2 GB bandwidth), a Python client (`supabase-py`) for the backend, built-in Row Level Security (RLS), and a REST API that requires zero connection pool management. For the SOTA StatWorks use case — storing user metadata, dataset references, and analysis results — a relational model with JSONB support (for analysis results) is the natural fit. The free tier comfortably supports hackathon-scale data volumes.

## Alternatives Considered

- **SQLite:** Zero-dependency, file-based. However, Render.com's free tier uses ephemeral filesystems — SQLite data is lost on every deploy or restart. Rejected because persistence is the entire point of adding a database.

- **Firebase Firestore:** NoSQL document store with real-time sync. However, the data model (users → datasets → analyses) is inherently relational, and Firestore's pricing model charges per read/write operation, which is harder to predict. Rejected for schema mismatch and cost unpredictability.

- **PlanetScale:** MySQL-compatible serverless database. However, the free tier was deprecated in 2024, and the cheapest paid tier adds unnecessary cost for a hackathon. Rejected for cost.

## Consequences

- **Short-term:**
  - Backend adds `supabase-py` dependency.
  - New module `backend/db/supabase.py` with functions: `upsert_user()`, `create_dataset()`, `create_analysis()`.
  - Three tables created: `users` (id, clerk_user_id, email, name), `datasets` (id, user_id, file_name, r2_key, created_at), `analyses` (id, dataset_id, result JSONB).
  - New env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` (backend only).
  - In-memory store transitions from primary storage to cache layer.
  - Build timeline increases by ~1–2 hours for schema setup and client integration.

- **Long-term:**
  - Datasets and analyses survive process restarts, deploys, and browser refreshes.
  - Judges can log in, reload, and still see previous results — "instant resume session" UX.
  - Identity mapping (Clerk ↔ Supabase) enables future features: analysis history, dataset sharing, usage analytics.
  - RLS can enforce that users only access their own data — though for v1 demo, RLS is optional.
  - PostgreSQL JSONB allows storing complex analysis results without schema migration for every field change.
