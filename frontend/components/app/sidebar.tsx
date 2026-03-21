"use client";

import { useAppStore } from "@/lib/store";
import { useRouter } from "next/navigation";
import type { ActiveView } from "@/lib/types";
import { useUser, UserButton } from "@clerk/nextjs";

/* ─── Sidebar Navigation Items ───────────────────────────────────────────── */

interface NavItem {
  id: ActiveView;
  label: string;
  icon: string;
  gated: boolean; // requires uploaded data to be accessible
  path: string;   // URL path for browser routing
}

const NAV_ITEMS: NavItem[] = [
  { id: "upload", label: "Upload", icon: "➕", gated: false, path: "/app" },
  { id: "chat", label: "AI Chat", icon: "🗨️", gated: true, path: "/app/chat" },
  { id: "data-viewer", label: "Data Viewer", icon: "📊", gated: true, path: "/app/viewer" },
  { id: "dashboard", label: "Monitor", icon: "📈", gated: true, path: "/app/monitor" },
  { id: "history", label: "History", icon: "📋", gated: false, path: "/app/history" },
];

/* ─── Component ──────────────────────────────────────────────────────────── */

export function Sidebar() {
  const { activeView, hasUploadedData, setActiveView } = useAppStore();
  const { user } = useUser();
  const router = useRouter();

  const handleNav = (item: NavItem) => {
    setActiveView(item.id);
    router.push(item.path);
  };

  return (
    <aside
      id="sidebar"
      className="sidebar"
    >
      {/* ── Logo ──────────────────────────────────────────────── */}
      <div className="sidebar-logo">
        <img src="/icon.png" alt="SW" className="sidebar-logo-icon" style={{ width: 32, height: 32 }} />
        <img src="/logo.png" alt="SOTA StatWorks" className="sidebar-logo-text" style={{ height: 36 }} />
      </div>

      {/* ── Nav Items ─────────────────────────────────────────── */}
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          const isDisabled = item.gated && !hasUploadedData;
          const isActive = activeView === item.id;

          return (
            <button
              key={item.id}
              id={`sidebar-${item.id}`}
              className={`sidebar-item ${isActive ? "sidebar-item--active" : ""} ${isDisabled ? "sidebar-item--disabled" : ""}`}
              onClick={() => !isDisabled && handleNav(item)}
              disabled={isDisabled}
              title={isDisabled ? `Upload data to unlock ${item.label}` : item.label}
            >
              <span className="sidebar-item-icon">{item.icon}</span>
              <span className="sidebar-item-label">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* ── Spacer ────────────────────────────────────────────── */}
      <div className="sidebar-spacer" />

      {/* ── User Account ──────────────────────────────────────── */}
      <div className="sidebar-account">
        <UserButton
          appearance={{
            elements: {
              avatarBox: "sidebar-avatar",
            },
          }}
        />
        {user && (
          <span className="sidebar-account-name">
            {user.firstName || "Account"}
          </span>
        )}
      </div>
    </aside>
  );
}
