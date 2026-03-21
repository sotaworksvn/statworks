# ADR-0004: Canva-Style Sidebar Navigation with Gated Feature Access

**Status:** proposed
**Date:** 2026-03-21
**Last updated:** 2026-03-21

**Chose:** Canva-style vertical sidebar navigation with gated feature access over the previous single-screen paradigm
**Rationale:** The product has evolved beyond a single-screen chat interface. New requirements demand multiple views (Upload, AI Chat, Data Viewer, SPSS/SmartPLS Dashboard), each serving a distinct user workflow. A persistent sidebar provides quick access to all views while maintaining visual context. The Canva-inspired design is familiar to creative/business users — the primary target audience.

## Context

The original SOTA StatWorks PRD (v0.2) mandated a single-screen paradigm. New requirements introduce four distinct feature areas:

1. **Upload** (Canva "Create") — Multi-file upload with history (5 files/batch, 20MB/file)
2. **AI Chat** (Canva "Home") — Existing chat + insight + simulation
3. **Data Viewer** (Canva "Classwork") — Browser-tab file viewer with in-place editing
4. **Dashboard** (Canva "Projects") — SPSS/SmartPLS ribbon-menu professional dashboard

Additionally:
- Features 2–4 are **gated**: they require at least one uploaded dataset before activation
- User account (Clerk) is accessible at all times via sidebar bottom
- Canva's "Template", "Brand", and "More" are excluded (no current function mapping)

## Decision

Replace the top `<AppHeader>` + full-page content layout with:
- A fixed **68px-wide vertical sidebar** on the left (expandable to 200px on hover)
- A fluid **content area** on the right that renders the active view
- Navigation state managed in Zustand (`activeView` field)
- Feature gating controlled by `hasUploadedData` boolean in Zustand

The sidebar order (top to bottom):
1. Upload (cloud icon)
2. AI Chat (home icon) — **default after first upload**
3. Data Viewer (table icon)
4. Dashboard (chart icon)
5. *(spacer)*
6. User Account (initials avatar, at bottom)

## Alternatives Considered

- **Tab bar at top**: Simpler but consumes vertical space on 1280px+ desktops. Conflicts with the data viewer's own horizontal tabs.
- **Keep single-screen, add modals**: Maintains PRD constraint but becomes cluttered with 4+ distinct feature areas. Poor UX for data viewer and dashboard which need full-screen space.
- **Full page routing (`/app/chat`, `/app/data`, etc.)**: Standard Next.js routing but loses the persistent sidebar context and requires page transitions.

## Consequences

- **Short-term**: Breaking change to frontend architecture. All existing app components (`chat-panel`, `insight-panel`, `simulation-bar`, `upload-zone`) must be reorganized under the new view routing system. Estimated 6–8 hours of frontend refactoring.
- **Long-term**: The sidebar pattern scales to future features without layout changes. New views can be added by creating a component and registering it in the sidebar.
- **Risk**: Sidebar on small viewports (<1024px) may need responsive handling. For v1 (desktop-only), this is acceptable.
- **PRD update required**: §5 Scope must move "Multi-page or tabbed navigation" from Out of Scope to In Scope.
