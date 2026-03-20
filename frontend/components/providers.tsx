"use client";

import { ClerkProvider, SignInButton, UserButton, useUser } from "@clerk/nextjs";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { useAuthSync } from "@/hooks/use-auth-sync";

interface ProvidersProps {
  children: React.ReactNode;
}

/**
 * Inner component that auto-syncs Clerk user to backend on login.
 * Must be inside ClerkProvider to access useUser().
 */
function AuthSync({ children }: { children: React.ReactNode }) {
  useAuthSync();
  return <>{children}</>;
}

export function Providers({ children }: ProvidersProps) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60_000,
            retry: 1,
          },
        },
      })
  );

  const clerkKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  // Auth is optional — app works in anonymous mode if key is missing
  if (!clerkKey) {
    return (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
  }

  return (
    <ClerkProvider publishableKey={clerkKey}>
      <QueryClientProvider client={queryClient}>
        <AuthSync>{children}</AuthSync>
      </QueryClientProvider>
    </ClerkProvider>
  );
}

// Re-export Clerk components for use in app components
export { SignInButton, UserButton };
