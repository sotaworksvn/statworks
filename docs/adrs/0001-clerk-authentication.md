# ADR-0001: Clerk for Authentication

**Status:** proposed
**Date:** 2026-03-20
**Last updated:** 2026-03-20

**Chose:** Clerk over Auth0, NextAuth.js, Supabase Auth
**Rationale:** Clerk provides prebuilt UI components (sign-in, user profile), native Google OAuth with minimal GCP setup, and session management that offloads all auth logic from the FastAPI backend. For a hackathon with a 20–30h build window, Clerk eliminates the need to build login pages, handle token refresh, or manage session cookies — saving an estimated 3–4 hours. The free tier supports up to 10,000 monthly active users, which is more than sufficient for demo and judging.

## Alternatives Considered

- **Auth0:** More enterprise-focused; requires more configuration for React integration; free tier limited to 7,000 MAU with fewer prebuilt UI components. Rejected because Clerk's drop-in `<SignIn />` and `<UserButton />` components are faster to integrate under time pressure.

- **NextAuth.js (Auth.js):** Open-source and framework-native for Next.js; however, requires manual session management, custom sign-in pages, and backend JWT verification setup. Rejected because it shifts auth implementation burden to the team rather than offloading it.

- **Supabase Auth:** Already using Supabase for metadata — could consolidate. However, Supabase Auth's React integration (`@supabase/auth-ui-react`) is less polished than Clerk's, and session handling requires more manual wiring. Rejected for UX quality: Clerk's prebuilt components look more professional out of the box.

## Consequences

- **Short-term:**
  - Frontend adds `@clerk/nextjs` dependency and wraps `app/layout.tsx` with `<ClerkProvider>`.
  - Backend extracts `clerk_user_id` from request headers (`x-clerk-user-id` or JWT verification) — thin middleware, no Clerk SDK needed on backend.
  - New env vars: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (frontend), `CLERK_SECRET_KEY` (backend, if JWT verification is used).
  - Build timeline increases by ~1–2 hours for integration.

- **Long-term:**
  - Clerk handles identity — backend never touches passwords, tokens, or session storage.
  - User identity enables dataset ownership, analysis history, and personalized UX ("Welcome back, {name}").
  - Vendor lock-in is low: Clerk's `user_id` is just a string stored in Supabase. Switching auth providers only requires changing the frontend wrapper and header extraction logic.
  - Auth does NOT affect the statistical engine or LLM layer — identity is decoupled from computation.
