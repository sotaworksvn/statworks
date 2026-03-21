# ADR-0006: In-Memory History Autosave

**Status:** proposed
**Date:** 2026-03-21
**Last updated:** 2026-03-21

**Chose:** In-memory Python dict over Supabase persistence
**Rationale:** Maintains the existing zero-latency architecture pattern established by `store.py`. All history entries are stored in a `dict[user_id][category] → list[HistoryEntry]` structure with LRU eviction at 200 entries per category per user. This avoids adding network latency to the autosave path and keeps the hackathon demo responsive. Trade-off: history is lost on server restart, which is acceptable for a demo context where sessions are short-lived.

## Alternatives Considered

- **Supabase persistence**: Durable but adds 30-80ms per autosave write. Would require new tables (history_entries) and schema migration. Rejected because autosave fires frequently (every chat response, every cell edit) and latency would accumulate.
- **Browser localStorage**: Client-side only, no cross-device access, 5MB limit per origin. Rejected because PDF export needs server-side access to all history for LLM analysis.
- **Hybrid (RAM + async Supabase write)**: Best of both worlds but adds implementation complexity. Deferred to v2 if persistence is needed beyond demo.

## Consequences

- **Short-term**: Zero-latency autosave from all 3 sources (Chat, Data Viewer, Dashboard). History page works immediately with no infrastructure changes.
- **Long-term**: If production use requires persistence, migrate to hybrid approach (ADR update needed). Current `HistoryEntry` dataclass maps cleanly to a Supabase table.
- **Risk**: Server restart clears all history. Mitigated by: (1) demo sessions are typically < 1 hour, (2) PDF export captures a permanent snapshot before the session ends.
