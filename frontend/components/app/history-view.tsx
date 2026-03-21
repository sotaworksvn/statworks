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

type HistoryTab = "chat" | "data";

interface HistoryEntry {
  id: string;
  category: string;
  title: string;
  created_at: string;
  snapshot_preview: string;
}

/* ─── Tab Config — Monitor removed ──────────────────────────────────────── */

const TABS: { key: HistoryTab; icon: string; label: string; urlSlug: string }[] = [
  { key: "chat", icon: "💬", label: "Phân tích", urlSlug: "chat" },
  { key: "data", icon: "📊", label: "Xem dữ liệu", urlSlug: "viewer" },
];

/* ─── Component ──────────────────────────────────────────────────────────── */

export function HistoryView() {
  const { setActiveView } = useAppStore();
  const { user } = useSafeUser();
  const router = useRouter();
  const params = useParams();
  const slug = params.slug as string[] | undefined;

  const getInitialTab = (): HistoryTab => {
    const sub = slug?.[1];
    if (sub === "viewer") return "data";
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

    const qp = new URLSearchParams({ category: tab });
    if (fromDate) qp.set("from_dt", new Date(fromDate).toISOString());
    if (toDate) {
      const toStr = toDate.includes("T") ? toDate : toDate + "T23:59:59";
      qp.set("to_dt", new Date(toStr).toISOString());
    }

    try {
      const res = await fetch(`${backendUrl}/api/history?${qp}`, {
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
    setFromDate(from.toISOString().slice(0, 16));
    setToDate(to.toISOString().slice(0, 16));
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const qp = new URLSearchParams();
      if (fromDate) qp.set("from_dt", new Date(fromDate).toISOString());
      if (toDate) {
        const toStr = toDate.includes("T") ? toDate : toDate + "T23:59:59";
        qp.set("to_dt", new Date(toStr).toISOString());
      }
      if (user?.id) qp.set("_clerk_user_id", user.id);
      const qs = qp.toString();

      const url = `${backendUrl}/api/history/export-pdf${qs ? "?" + qs : ""}`;
      const response = await fetch(url, {
        headers: user?.id ? { "x-clerk-user-id": user.id } : {},
      });

      if (!response.ok) {
        const errText = await response.text();
        alert(`Export thất bại: ${errText}`);
        return;
      }

      const disposition = response.headers.get("Content-Disposition");
      let filename = "sota_statworks_report.pdf";
      if (disposition) {
        const match = disposition.match(/filename=([^;]+)/);
        if (match) filename = match[1].trim().replace(/"/g, "");
        if (!filename.toLowerCase().endsWith(".pdf")) filename += ".pdf";
      }

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
      alert("Không thể export PDF. Vui lòng thử lại.");
    } finally {
      setIsExporting(false);
    }
  };

  const handleClickEntry = (entry: HistoryEntry) => {
    const viewMap: Record<string, "chat" | "data-viewer"> = {
      chat: "chat",
      data: "data-viewer",
    };
    setActiveView(viewMap[entry.category] || "chat");
  };

  const formatTimestamp = (iso: string) => {
    try {
      const d = new Date(iso);
      const now = new Date();
      const diff = now.getTime() - d.getTime();
      const mins = Math.floor(diff / 60000);
      if (mins < 1) return "Vừa xong";
      if (mins < 60) return `${mins} phút trước`;
      const hours = Math.floor(mins / 60);
      if (hours < 24) return `${hours} giờ trước`;
      return d.toLocaleString("vi-VN", {
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
            <h2 className="hist-title">Lịch Sử</h2>
            <p className="hist-subtitle">
              {entries.length > 0
                ? `${entries.length} mục`
                : "Nhật ký hoạt động"}
            </p>
          </div>
        </div>
        <button className="hist-export" onClick={handleExport} disabled={isExporting}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
          {isExporting ? "Đang tạo…" : "Export PDF"}
        </button>
      </div>

      {/* ── Ribbon Tabs — Only Chat and Viewer ─────────────── */}
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
              <span className="hist-date-lbl">Từ</span>
              <input type="datetime-local" value={fromDate} onChange={(e) => setFromDate(e.target.value)} className="hist-date-input" />
            </div>
            <span className="hist-date-sep">—</span>
            <div className="hist-date-field">
              <span className="hist-date-lbl">Đến</span>
              <input type="datetime-local" value={toDate} onChange={(e) => setToDate(e.target.value)} className="hist-date-input" />
            </div>
          </div>
          <div className="hist-presets">
            {[
              { label: "5p", mins: 5 },
              { label: "30p", mins: 30 },
              { label: "1h", mins: 60 },
              { label: "3h", mins: 180 },
              { label: "Hôm nay", mins: 0 },
              { label: "7 ngày", mins: 10080 },
              { label: "Tất cả", mins: null },
            ].map((p) => (
              <button key={p.label} onClick={() => {
                if (p.mins === 0) {
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
            <p>Đang tải…</p>
          </div>
        ) : entries.length === 0 ? (
          <div className="hist-empty">
            <div className="hist-empty-icon">{activeTabConfig.icon}</div>
            <h3 className="hist-empty-title">Chưa có lịch sử {activeTabConfig.label}</h3>
            <p className="hist-empty-desc">
              {tab === "chat"
                ? "Phân tích hồ sơ với AI — các cuộc hội thoại được lưu tự động."
                : "Xem dữ liệu trong Data Viewer — lịch sử được lưu tự động."}
            </p>
            <button className="hist-empty-cta" onClick={() => setActiveView(tab === "chat" ? "chat" : "data-viewer")}>
              Đến {activeTabConfig.label} →
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
