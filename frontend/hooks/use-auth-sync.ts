"use client";

import { useEffect, useRef } from "react";
import { useUser } from "@clerk/nextjs";
import { useAppStore } from "@/lib/store";
import { syncUser } from "@/lib/api";

/**
 * Auto-sync Clerk user to backend on login.
 *
 * Flow: Clerk login → useUser() → POST /sync-user → Supabase.users
 *
 * This hook runs once when the Clerk user changes (login/logout).
 * It caches the sync result to avoid repeated calls.
 */
export function useAuthSync() {
  const { user, isSignedIn } = useUser();
  const { setUser } = useAppStore();
  const hasSynced = useRef(false);

  useEffect(() => {
    if (!isSignedIn || !user || hasSynced.current) {
      if (!isSignedIn) {
        setUser(null);
        hasSynced.current = false;
      }
      return;
    }

    // Update Zustand with Clerk user data
    setUser({
      id: user.id,
      email: user.primaryEmailAddress?.emailAddress ?? null,
      firstName: user.firstName ?? null,
      lastName: user.lastName ?? null,
      imageUrl: user.imageUrl ?? null,
    });

    // Sync to backend (fire-and-forget — non-blocking)
    syncUser(
      user.id,
      user.primaryEmailAddress?.emailAddress ?? undefined,
      [user.firstName, user.lastName].filter(Boolean).join(" ") || undefined
    )
      .then(() => {
        hasSynced.current = true;
      })
      .catch((err) => {
        // Sync failure is non-fatal — user can still use the app
        console.warn("User sync failed (non-fatal):", err);
      });
  }, [isSignedIn, user, setUser]);
}
