"use client";

import { useEffect, useRef } from "react";
import { useAppStore } from "@/lib/store";
import { useUser, SignIn } from "@clerk/nextjs";
import { useRouter, useParams } from "next/navigation";
import { Sidebar } from "@/components/app/sidebar";
import { UploadZone } from "@/components/app/upload-zone";
import { ChatPanel } from "@/components/app/chat-panel";
import { InsightPanel } from "@/components/app/insight-panel";
import { SimulationBar } from "@/components/app/simulation-bar";
import { DataViewer } from "@/components/app/data-viewer";
import { Dashboard } from "@/components/app/dashboard";
import { HistoryView } from "@/components/app/history-view";
import { Toaster } from "@/components/ui/sonner";
import Image from "next/image";

/* ─── URL ↔ View mapping ─────────────────────────────────────────────────── */

import type { ActiveView } from "@/lib/types";

interface RouteState {
  view: ActiveView;
  subTab?: string; // history tab or monitor tab
}

/** Map URL slug segments → Zustand view + optional sub-tab */
function slugToRoute(slug: string[] | undefined): RouteState {
  if (!slug || slug.length === 0) return { view: "upload" };

  const primary = slug[0];
  const secondary = slug[1];

  switch (primary) {
    case "chat":
      return { view: "chat" };
    case "viewer":
      return { view: "data-viewer" };
    case "monitor":
      if (secondary === "impact-analysis") return { view: "dashboard", subTab: "smartpls" };
      return { view: "dashboard", subTab: secondary === "data-analysis" ? "spss" : "spss" };
    case "history":
      if (secondary === "chat") return { view: "history", subTab: "chat" };
      if (secondary === "viewer") return { view: "history", subTab: "data" };
      if (secondary === "monitor") return { view: "history", subTab: "dashboard" };
      return { view: "history", subTab: "chat" };
    default:
      return { view: "upload" };
  }
}

/** Map Zustand view → URL path segments */
function viewToPath(view: ActiveView, subTab?: string): string {
  switch (view) {
    case "upload":
      return "/app";
    case "chat":
      return "/app/chat";
    case "data-viewer":
      return "/app/viewer";
    case "dashboard":
      if (subTab === "smartpls") return "/app/monitor/impact-analysis";
      return "/app/monitor/data-analysis";
    case "history":
      if (subTab === "data") return "/app/history/viewer";
      if (subTab === "dashboard") return "/app/history/monitor";
      return "/app/history/chat";
    default:
      return "/app";
  }
}

/* ─── Page Component ──────────────────────────────────────────────────────── */

export default function AppPage() {
  const { activeView, setActiveView, fileId } = useAppStore();
  const { isSignedIn, isLoaded } = useUser();
  const router = useRouter();
  const params = useParams();
  const slug = params.slug as string[] | undefined;
  const initializedRef = useRef(false);

  // ── On mount: read URL → set Zustand state ──
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    const { view } = slugToRoute(slug);
    setActiveView(view);
  }, [slug, setActiveView]);

  // ── When activeView changes → push URL ──
  const prevViewRef = useRef(activeView);
  useEffect(() => {
    if (!initializedRef.current) return;
    if (prevViewRef.current === activeView) return;
    prevViewRef.current = activeView;

    const path = viewToPath(activeView);
    router.push(path);
  }, [activeView, router]);

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

  // ── Signed in → sidebar + content layout ──
  return (
    <div className="app-layout">
      <Sidebar />

      <div className="app-content">
        {/* ── Upload View ────────────────────────────────── */}
        {activeView === "upload" && (
          <div className="app-view app-view--upload">
            <UploadZone />
          </div>
        )}

        {/* ── AI Chat View ───────────────────────────────── */}
        {activeView === "chat" && (
          <div className="app-view app-view--chat">
            {fileId ? (
              <>
                <main className="chat-layout">
                  <ChatPanel />
                  <InsightPanel />
                </main>
                <SimulationBar />
              </>
            ) : (
              <div className="app-view-empty">
                <div className="app-view-empty-icon">💬</div>
                <h3>No Dataset Loaded</h3>
                <p>Upload a dataset first, then ask questions about your data here.</p>
              </div>
            )}
          </div>
        )}

        {/* ── Data Viewer ────────────────────────────────── */}
        {activeView === "data-viewer" && (
          <div className="app-view app-view--data-viewer">
            <DataViewer />
          </div>
        )}

        {/* ── Monitor ─────────────────────────────────────── */}
        {activeView === "dashboard" && (
          <div className="app-view app-view--dashboard">
            <Dashboard />
          </div>
        )}

        {/* ── History ─────────────────────────────────────── */}
        {activeView === "history" && (
          <div className="app-view app-view--history">
            <HistoryView />
          </div>
        )}
      </div>

      <Toaster position="bottom-right" />
    </div>
  );
}
