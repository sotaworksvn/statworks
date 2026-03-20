"use client";

import { useState, useCallback, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { useUser, SignIn } from "@clerk/nextjs";
import { AppHeader } from "@/components/app/header";
import { UploadZone } from "@/components/app/upload-zone";
import { ChatPanel } from "@/components/app/chat-panel";
import { InsightPanel } from "@/components/app/insight-panel";
import { SimulationBar } from "@/components/app/simulation-bar";
import { Toaster } from "@/components/ui/sonner";
import Image from "next/image";

export default function AppPage() {
  const { fileId, resetDataset } = useAppStore();
  const { isSignedIn, isLoaded } = useUser();
  const [showUpload, setShowUpload] = useState(false);

  const handleUploadClick = useCallback(() => {
    if (fileId) {
      resetDataset();
    }
    setShowUpload(true);
  }, [fileId, resetDataset]);

  // When a dataset is loaded and showUpload was true, hide upload overlay
  useEffect(() => {
    if (fileId && showUpload) {
      setShowUpload(false);
    }
  }, [fileId, showUpload]);

  const showUploadZone = !fileId || showUpload;

  // ── Loading state while Clerk initializes ──
  if (!isLoaded) {
    return (
      <div className="flex h-screen items-center justify-center bg-white">
        <div className="text-gray-400 text-sm animate-pulse">Loading…</div>
      </div>
    );
  }

  // ── Not signed in → show Clerk sign-in ──
  if (!isSignedIn) {
    return (
      <div className="flex h-screen flex-col items-center justify-center bg-white gap-8">
        <div className="flex flex-col items-center gap-4">
          <Image src="/logo.png" alt="SOTA StatWorks" width={200} height={56} />
          <p className="text-gray-500 text-sm">
            Sign in to start analyzing your data
          </p>
        </div>
        <SignIn
          routing="hash"
          appearance={{
            elements: {
              rootBox: "mx-auto",
              card: "shadow-lg border border-gray-100 rounded-2xl",
            },
          }}
        />
      </div>
    );
  }

  // ── Signed in → show app ──
  return (
    <>
      <AppHeader onUploadClick={handleUploadClick} />

      {showUploadZone ? (
        <UploadZone />
      ) : (
        <>
          <main className="flex flex-1 overflow-hidden">
            {/* Chat panel — 35% */}
            <ChatPanel />
            {/* Insight panel — 65% */}
            <InsightPanel />
          </main>
          <SimulationBar />
        </>
      )}

      <Toaster position="bottom-right" />
    </>
  );
}
