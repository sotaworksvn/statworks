"use client";

import { useEffect, useRef } from "react";
import { useAppStore } from "@/lib/store";
import { useUser, SignIn } from "@clerk/nextjs";
import { useRouter, useParams } from "next/navigation";
import { Sidebar } from "@/components/app/sidebar";
import { UploadZone } from "@/components/app/upload-zone";
import { ChatPanel } from "@/components/app/chat-panel";
import { InsightPanel } from "@/components/app/insight-panel";
import { DataViewer } from "@/components/app/data-viewer";
import { HistoryView } from "@/components/app/history-view";
import { Toaster } from "@/components/ui/sonner";
import Image from "next/image";

const HAS_CLERK_KEY = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

/** Safe useUser — returns anonymous defaults when ClerkProvider is absent */
function useSafeUser() {
  if (HAS_CLERK_KEY) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useUser();
  }
  return { isSignedIn: true as const, isLoaded: true, user: null };
}

/* ─── URL ↔ View mapping ─────────────────────────────────────────────────── */

import type { ActiveView } from "@/lib/types";

interface RouteState {
  view: ActiveView;
  subTab?: string;
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
    case "history":
      if (secondary === "uploads") return { view: "history", subTab: "uploads" };
      if (secondary === "chat") return { view: "history", subTab: "chat" };
      return { view: "history", subTab: "uploads" };
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
    case "history":
      if (subTab === "chat") return "/app/history/chat";
      return "/app/history/uploads";
    default:
      return "/app";
  }
}

/* ─── Page Component ──────────────────────────────────────────────────────── */

export default function AppPage() {
  const { activeView, setActiveView, fileId } = useAppStore();
  const { isSignedIn, isLoaded } = useSafeUser();
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
        <div className="text-gray-400 text-sm animate-pulse">Đang tải…</div>
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
            Đăng nhập để bắt đầu dự đoán học bổng
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
              <main className="chat-layout">
                <ChatPanel />
                <InsightPanel />
              </main>
            ) : (
              <div className="app-view-empty">
                <div className="app-view-empty-icon">💬</div>
                <h3>Chưa có dữ liệu</h3>
                <p>Upload bảng điểm trước, sau đó AI sẽ dự đoán học bổng cho bạn.</p>
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
