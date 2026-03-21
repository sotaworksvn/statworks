"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useAppStore } from "@/lib/store";
import { useUser } from "@clerk/nextjs";
import { useRouter, useParams } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";

const HAS_CLERK_KEY = !!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

function useSafeUser() {
  if (HAS_CLERK_KEY) {
    // eslint-disable-next-line react-hooks/rules-of-hooks
    return useUser();
  }
  return { user: null };
}

/* ─── Types ──────────────────────────────────────────────────────────────── */

type HistoryTab = "uploads" | "chat";

interface ChatHistoryEntry {
  id: string;
  category: string;
  title: string;
  created_at: string;
  snapshot_preview: string;
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function formatFileSize(bytes: number): string {
  if (!bytes || bytes === 0) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTimestamp(iso: string): string {
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
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export function HistoryView() {
  const { setActiveView, uploadedFiles } = useAppStore();
  const { user } = useSafeUser();
  const router = useRouter();
  const params = useParams();
  const slug = params.slug as string[] | undefined;

  const getInitialTab = (): HistoryTab => {
    const sub = slug?.[1];
    if (sub === "chat") return "chat";
    return "uploads"; // default to uploads tab
  };

  const [tab, setTab] = useState<HistoryTab>(getInitialTab);

  // Chat history — fetched from backend
  const [chatEntries, setChatEntries] = useState<ChatHistoryEntry[]>([]);
  const [isLoadingChat, setIsLoadingChat] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");

  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
  const fetchRef = useRef(0);

  const fetchChatHistory = useCallback(async () => {
    const fetchId = ++fetchRef.current;
    setIsLoadingChat(true);

    const qp = new URLSearchParams({ category: "chat" });
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
      setChatEntries(data.entries || []);
    } catch {
      if (fetchId === fetchRef.current) setChatEntries([]);
    } finally {
      if (fetchId === fetchRef.current) setIsLoadingChat(false);
    }
  }, [fromDate, toDate, user?.id, backendUrl]);

  // Only fetch chat history when chat tab is active
  useEffect(() => {
    if (tab === "chat") {
      fetchChatHistory();
    }
  }, [tab, fetchChatHistory]);

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

  const switchTab = (newTab: HistoryTab) => {
    setTab(newTab);
    router.push(`/app/history/${newTab}`);
  };

  return (
    <div className="hist">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="hist-header">
        <div className="hist-header-left">
          <div className="hist-icon-wrap">🕐</div>
          <div>
            <h2 className="hist-title">Lịch Sử</h2>
            <p className="hist-subtitle">
              {tab === "uploads"
                ? `${uploadedFiles.length} file đã upload`
                : "Nhật ký phân tích AI"}
            </p>
          </div>
        </div>
        {tab === "chat" && (
          <button className="hist-export" onClick={handleExport} disabled={isExporting}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <polyline points="10 9 9 9 8 9"/>
            </svg>
            {isExporting ? "Đang tạo…" : "Export PDF"}
          </button>
        )}
      </div>

      {/* ── Tabs — Uploads + Chat ─────────────────────────── */}
      <div className="hist-tabs">
        <button
          className={`hist-tab${tab === "uploads" ? " hist-tab--on" : ""}`}
          onClick={() => switchTab("uploads")}
        >
          <span className="hist-tab-ico">📊</span>
          <span>File đã upload</span>
        </button>
        <button
          className={`hist-tab${tab === "chat" ? " hist-tab--on" : ""}`}
          onClick={() => switchTab("chat")}
        >
          <span className="hist-tab-ico">💬</span>
          <span>Phân tích</span>
        </button>
      </div>

      {/* ── Content ────────────────────────────────────────── */}
      <AnimatePresence mode="wait">
        {tab === "uploads" ? (
          <motion.div
            key="uploads"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
            className="hist-content"
          >
            {uploadedFiles.length === 0 ? (
              <div className="hist-empty">
                <div className="hist-empty-icon">📁</div>
                <h3 className="hist-empty-title">Chưa có file nào</h3>
                <p className="hist-empty-desc">
                  Upload file bảng điểm (.xlsx, .xls, .csv) để bắt đầu dự đoán học bổng.
                </p>
                <button className="hist-empty-cta" onClick={() => setActiveView("upload")}>
                  Upload ngay →
                </button>
              </div>
            ) : (
              <div className="hist-list">
                {[...uploadedFiles].reverse().map((file, i) => (
                  <motion.div
                    key={file.id}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.04 }}
                    className="hist-card"
                    onClick={() => setActiveView("data-viewer")}
                    style={{ cursor: "pointer" }}
                  >
                    <div className="hist-card-left">
                      {/* File type icon */}
                      <div
                        className="hist-card-dot"
                        style={{
                          width: 32, height: 32, borderRadius: 8,
                          background: file.type === ".csv" ? "#e0f2fe" : "#f0fdf4",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          fontSize: 16, flexShrink: 0,
                        }}
                      >
                        {file.type === ".csv" ? "📄" : "📊"}
                      </div>
                      <div className="hist-card-info">
                        <div className="hist-card-title">{file.name}</div>
                        <div className="hist-card-preview">
                          {file.row_count} dòng · {file.columns.length} cột
                          {file.file_size ? ` · ${formatFileSize(file.file_size)}` : ""}
                        </div>
                      </div>
                    </div>
                    <div className="hist-card-right">
                      <span className="hist-card-time">{formatTimestamp(file.uploaded_at)}</span>
                      <span className="hist-card-arrow">›</span>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="chat"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
          >
            {/* ── Time Filter (chat only) ──────────────────── */}
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

            {/* Chat history entries */}
            <div className="hist-content">
              {isLoadingChat ? (
                <div className="hist-loading">
                  <div className="hist-spinner" />
                  <p>Đang tải…</p>
                </div>
              ) : chatEntries.length === 0 ? (
                <div className="hist-empty">
                  <div className="hist-empty-icon">💬</div>
                  <h3 className="hist-empty-title">Chưa có lịch sử phân tích</h3>
                  <p className="hist-empty-desc">
                    Phân tích hồ sơ với AI — các cuộc hội thoại được lưu tự động.
                  </p>
                  <button className="hist-empty-cta" onClick={() => setActiveView("chat")}>
                    Đến Phân tích →
                  </button>
                </div>
              ) : (
                <div className="hist-list">
                  {chatEntries.map((entry, i) => (
                    <div
                      key={entry.id}
                      className="hist-card"
                      onClick={() => setActiveView("chat")}
                      style={{ animationDelay: `${i * 0.03}s`, cursor: "pointer" }}
                    >
                      <div className="hist-card-left">
                        <div className="hist-card-dot" data-cat="chat" />
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
