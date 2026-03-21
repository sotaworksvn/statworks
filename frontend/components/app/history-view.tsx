"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAppStore } from "@/lib/store";
import { useUser } from "@clerk/nextjs";
import { useRouter, useParams } from "next/navigation";

const HAS_CLERK_KEY = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

/** Safe useUser — returns anonymous defaults when ClerkProvider is absent */
function useSafeUser() {
  if (HAS_CLERK_KEY) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useUser();
  }
  return { user: null };
}

/* ─── Types ──────────────────────────────────────────────────────────────── */

type HistoryTab = "chat" | "data" | "dashboard";

interface HistoryEntry {
  id: string;
  category: string;
  title: string;
  created_at: string;
  snapshot_preview: string;
}

/* ─── Tab Config ─────────────────────────────────────────────────────────── */

const TABS: { key: HistoryTab; icon: string; label: string; urlSlug: string }[] = [
  { key: "chat", icon: "💬", label: "AI Chat", urlSlug: "chat" },
  { key: "data", icon: "📊", label: "Data Edits", urlSlug: "viewer" },
  { key: "dashboard", icon: "🎯", label: "Monitor", urlSlug: "monitor" },
];

/* ─── Component ──────────────────────────────────────────────────────────── */

export function HistoryView() {
  const { setActiveView } = useAppStore();
  const { user } = useSafeUser();
  const router = useRouter();
  const params = useParams();
  const slug = params.slug as string[] | undefined;

  // Read initial tab from URL slug: /app/history/chat | /app/history/viewer | /app/history/monitor
  const getInitialTab = (): HistoryTab => {
    const sub = slug?.[1];
    if (sub === "viewer") return "data";
    if (sub === "monitor") return "dashboard";
    return "chat";
  };

  const [tab, setTab] = useState<HistoryTab>(getInitialTab);
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const fetchRef = useRef(0);

  const fetchEntries = useCallback(async () => {
    const fetchId = ++fetchRef.current;
    setIsLoading(true);

    const params = new URLSearchParams({ category: tab });
    if (fromDate) params.set("from_dt", new Date(fromDate).toISOString());
    if (toDate) {
      // If datetime-local (has T), use as-is; if date-only, add end of day
      const toStr = toDate.includes("T") ? toDate : toDate + "T23:59:59";
      params.set("to_dt", new Date(toStr).toISOString());
    }

    try {
      const res = await fetch(`${backendUrl}/api/history?${params}`, {
        headers: user?.id ? { "x-clerk-user-id": user.id } : {},
      });
      if (fetchId !== fetchRef.current) return;
      const data = res.ok ? await res.json() : { entries: [] };
      setEntries(data.entries || []);
    } catch {
      if (fetchId === fetchRef.current) setEntries([]);
    } finally {
      if (fetchId === fetchRef.current) setIsLoading(false);
    }
  }, [tab, fromDate, toDate, user?.id, backendUrl]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const setPreset = (minutes: number | null) => {
    if (minutes === null) { setFromDate(""); setToDate(""); return; }
    const to = new Date();
    const from = new Date(to.getTime() - minutes * 60 * 1000);
    // Use ISO datetime strings for sub-day precision
    setFromDate(from.toISOString().slice(0, 16));
    setToDate(to.toISOString().slice(0, 16));
  };

  const handleExport = async () => {
    setIsExporting(true);

    try {
      // Build GET URL with query params
      const params = new URLSearchParams();
      if (fromDate) params.set("from_dt", new Date(fromDate).toISOString());
      if (toDate) {
        const toStr = toDate.includes("T") ? toDate : toDate + "T23:59:59";
        params.set("to_dt", new Date(toStr).toISOString());
      }
      if (user?.id) params.set("_clerk_user_id", user.id);
      const qs = params.toString();

      const url = `${backendUrl}/api/history/export-pdf${qs ? "?" + qs : ""}`;
      const response = await fetch(url, {
        headers: user?.id ? { "x-clerk-user-id": user.id } : {},
      });

      if (!response.ok) {
        const errText = await response.text();
        alert(`Export failed: ${errText}`);
        return;
      }

      // Get filename from Content-Disposition header, fallback to default
      const disposition = response.headers.get("Content-Disposition");
      let filename = "sota_statworks_report.pdf";
      if (disposition) {
        const match = disposition.match(/filename=([^;]+)/);
        if (match) filename = match[1].trim().replace(/"/g, "");
        // Ensure .pdf extension
        if (!filename.toLowerCase().endsWith(".pdf")) filename += ".pdf";
      }

      // Create blob and trigger download
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("PDF export error:", err);
      alert("Failed to export PDF. Please try again.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleClickEntry = (entry: HistoryEntry) => {
    const viewMap: Record<string, "chat" | "data-viewer" | "dashboard"> = {
      chat: "chat", data: "data-viewer", dashboard: "dashboard",
    };
    setActiveView(viewMap[entry.category] || "chat");
  };

  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 1) return "Just now";
      if (mins < 60) return `${mins}m ago`;
      const hours = Math.floor(mins / 60);
      if (hours < 24) return `${hours}h ago`;
      return d.toLocaleString("en-GB", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
    } catch { return iso; }
  };

  const activeTabConfig = TABS.find((t) => t.key === tab)!;

  return (
    <div className="hist">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="hist-header">
        <div className="hist-header-left">
          <div className="hist-icon-wrap">🕐</div>
          <div>
            <h2 className="hist-title">History</h2>
            <p className="hist-subtitle">
              {entries.length > 0
                ? `${entries.length} entr${entries.length !== 1 ? "ies" : "y"}`
                : "Activity log"}
            </p>
          </div>
        </div>
        <button className="hist-export" onClick={handleExport} disabled={isExporting}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          {isExporting ? "Generating…" : "Export PDF"}
        </button>
      </div>

      {/* ── Ribbon Tabs ────────────────────────────────────── */}
      <div className="hist-tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`hist-tab${tab === t.key ? " hist-tab--on" : ""}`}
            onClick={() => {
              setTab(t.key);
              router.push(`/app/history/${t.urlSlug}`);
            }}
          >
            <span className="hist-tab-ico">{t.icon}</span>
            <span>{t.label}</span>
          </button>
        ))}
      </div>

      {/* ── Time Filter ────────────────────────────────────── */}
      <div className="hist-filter">
        <div className="hist-filter-row">
          <div className="hist-filter-dates">
            <div className="hist-date-field">
              <span className="hist-date-lbl">From</span>
              <input type="datetime-local" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="hist-date-input" />
            </div>
            <span className="hist-date-sep">—</span>
            <div className="hist-date-field">
              <span className="hist-date-lbl">To</span>
              <input type="datetime-local" value={toDate} onChange={(e) => setToDate(e.target.value)} className="hist-date-input" />
            </div>
          </div>
          <div className="hist-presets">
            {[
              { label: "5m", mins: 5 },
              { label: "10m", mins: 10 },
              { label: "30m", mins: 30 },
              { label: "1h", mins: 60 },
              { label: "3h", mins: 180 },
              { label: "12h", mins: 720 },
              { label: "Today", mins: 0 },
              { label: "7d", mins: 10080 },
              { label: "30d", mins: 43200 },
              { label: "All", mins: null },
            ].map((p) => (
              <button key={p.label} onClick={() => {
                if (p.mins === 0) {
                  // "Today" special case: from start of today
                  const now = new Date();
                  const startOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
                  setFromDate(startOfDay.toISOString().slice(0, 16));
                  setToDate(now.toISOString().slice(0, 16));
                } else {
                  setPreset(p.mins);
                }
              }} className="hist-preset">{p.label}</button>
            ))}
          </div>
        </div>
      </div>

      {/* ── Content ────────────────────────────────────────── */}
      <div className="hist-content">
        {isLoading ? (
          <div className="hist-loading">
            <div className="hist-spinner" />
            <p>Loading…</p>
          </div>
        ) : entries.length === 0 ? (
          <div className="hist-empty">
            <div className="hist-empty-icon">{activeTabConfig.icon}</div>
            <h3 className="hist-empty-title">No {activeTabConfig.label} history</h3>
            <p className="hist-empty-desc">
              {tab === "chat"
                ? "Chat with AI — sessions are automatically saved."
                : tab === "data"
                ? "Edit data in the Data Viewer — changes are saved automatically."
                : "Run analyses in Dashboard — results are saved automatically."}
            </p>
            <button className="hist-empty-cta" onClick={() => setActiveView(tab === "chat" ? "chat" : tab === "data" ? "data-viewer" : "dashboard")}>
              Go to {activeTabConfig.label} →
            </button>
          </div>
        ) : (
          <div className="hist-list">
            {entries.map((entry, i) => (
              <div key={entry.id} className="hist-card" onClick={() => handleClickEntry(entry)}
                style={{ animationDelay: `${i * 0.03}s` }}>
                <div className="hist-card-left">
                  <div className="hist-card-dot" data-cat={entry.category} />
                  <div className="hist-card-info">
                    <div className="hist-card-title">{entry.title}</div>
                    {entry.snapshot_preview && (
                      <div className="hist-card-preview">{entry.snapshot_preview}</div>
                    )}
                  </div>
                </div>
                <div className="hist-card-right">
                  <span className="hist-card-time">{formatTimestamp(entry.created_at)}</span>
                  <span className="hist-card-arrow">›</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
