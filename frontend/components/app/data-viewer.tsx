"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useAppStore } from "@/lib/store";
import { useUser } from "@clerk/nextjs";

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

interface FileTab {
  id: string;
  name: string;
  type: string;
}

interface TabContent {
  columns: string[];
  rows: Record<string, unknown>[];
  totalRows: number;
  contextText?: string | null;
}

type FetchStatus = "idle" | "loading" | "ok" | "error";

// Module-level scroll position storage (persists across component unmount/remount)
const _scrollPositions: Record<string, number> = {};

/* ─── Component ──────────────────────────────────────────────────────────── */

export function DataViewer() {
  const { uploadedFiles, removeUploadedFile, localParsedData } = useAppStore();
  const { user } = useSafeUser();
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [tabData, setTabData] = useState<Record<string, TabContent>>({});
  const [closedTabs, setClosedTabs] = useState<Set<string>>(new Set());
  const [fetchStatus, setFetchStatus] = useState<FetchStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRecoverable, setIsRecoverable] = useState(true);

  // Track which IDs have been successfully fetched
  const fetchedIds = useRef<Set<string>>(new Set());

  // Build file tabs from uploaded files
  const fileTabs: FileTab[] = uploadedFiles
    .filter((f) => !closedTabs.has(f.id))
    .map((f) => ({ id: f.id, name: f.name, type: f.type }));

  // Set active tab to first if none set
  useEffect(() => {
    if (!activeTabId && fileTabs.length > 0) {
      setActiveTabId(fileTabs[0].id);
    }
  }, [fileTabs.length, activeTabId]);

  // Fetch function — extracted for retry support
  const doFetch = useCallback((id: string) => {
    setFetchStatus("loading");
    setErrorMessage(null);
    setIsRecoverable(true);

    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);

    fetch(`${backendUrl}/api/data/${id}/content?limit=500`, {
      signal: controller.signal,
      headers: user?.id ? { "x-clerk-user-id": user.id } : {},
    })
      .then((res) => {
        clearTimeout(timeout);
        if (res.status === 404) {
          const err = new Error("This dataset is no longer available on the server. It was cleared when the server restarted. Please upload your file again.");
          err.name = "NotFound";
          throw err;
        }
        if (!res.ok) throw new Error(`Server error (${res.status})`);
        return res.json();
      })
      .then((data) => {
        fetchedIds.current.add(id);
        setTabData((prev) => ({
          ...prev,
          [id]: {
            columns: data.columns?.map((c: { name: string }) => c.name) || [],
            rows: data.rows || [],
            totalRows: data.row_count ?? data.rows?.length ?? 0,
            contextText: data.context_text,
          },
        }));
        setFetchStatus("ok");
      })
      .catch((err) => {
        clearTimeout(timeout);
        if (err.name === "AbortError") {
          setErrorMessage("Request timed out — the server may be slow or unreachable.");
          setIsRecoverable(true);
        } else if (err.name === "NotFound") {
          setErrorMessage(err.message);
          setIsRecoverable(false);
          fetchedIds.current.add(id);
          removeUploadedFile(id);
        } else {
          setErrorMessage(err.message || "Failed to load dataset content.");
          setIsRecoverable(true);
        }
        setFetchStatus("error");
      });

    return () => {
      clearTimeout(timeout);
      controller.abort();
    };
  }, [user?.id, removeUploadedFile]);

  const tabDataRef = useRef(tabData);
  tabDataRef.current = tabData;

  // Fetch content for active tab
  useEffect(() => {
    if (!activeTabId) return;

    // Priority 1: Check local SheetJS-parsed data (instant, 0ms)
    const localData = localParsedData[activeTabId];
    if (localData && !tabDataRef.current[activeTabId]) {
      setTabData((prev) => ({
        ...prev,
        [activeTabId]: {
          columns: localData.columns,
          rows: localData.rows,
          totalRows: localData.rows.length,
          contextText: null,
        },
      }));
      fetchedIds.current.add(activeTabId);
      setFetchStatus("ok");
      setErrorMessage(null);
      return;
    }

    // Priority 2: Already fetched from server — show cached data
    if (tabDataRef.current[activeTabId]) {
      setFetchStatus("ok");
      setErrorMessage(null);
      return;
    }

    // Priority 3: Already marked as fetched (e.g., 404) — keep error state
    if (fetchedIds.current.has(activeTabId)) {
      return;
    }

    // Priority 4: Fetch from server
    return doFetch(activeTabId);
  }, [activeTabId, doFetch, localParsedData]);

  const handleRetry = () => {
    if (activeTabId) {
      fetchedIds.current.delete(activeTabId);
      doFetch(activeTabId);
    }
  };

  const handleCloseTab = useCallback(
    (id: string) => {
      setClosedTabs((prev) => new Set([...prev, id]));
      fetchedIds.current.delete(id);
      setTabData((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (activeTabId === id) {
        const remaining = fileTabs.filter((t) => t.id !== id);
        setActiveTabId(remaining.length > 0 ? remaining[0].id : null);
      }
    },
    [activeTabId, fileTabs],
  );

  const activeData = activeTabId ? tabData[activeTabId] : null;
  const activeFile = fileTabs.find((t) => t.id === activeTabId);

  if (fileTabs.length === 0) {
    return (
      <div className="data-viewer-empty">
        <div className="data-viewer-empty-icon">📊</div>
        <h3>Chưa có dữ liệu</h3>
        <p>Upload hồ sơ để xem nội dung tại đây.</p>
      </div>
    );
  }

  return (
    <div className="data-viewer">
      {/* ── Tab Bar ─────────────────────────────────────────── */}
      <div className="data-viewer-tabs">
        {fileTabs.map((tab) => (
          <div
            key={tab.id}
            className={`data-viewer-tab ${activeTabId === tab.id ? "data-viewer-tab--active" : ""}`}
            onClick={() => setActiveTabId(tab.id)}
          >
            <span className="data-viewer-tab-icon">
              {tab.type === ".xlsx" || tab.type === ".csv" ? "📄" : tab.type === ".docx" ? "📝" : "📑"}
            </span>
            <span className="data-viewer-tab-name">{tab.name}</span>
            <button
              className="data-viewer-tab-close"
              onClick={(e) => {
                e.stopPropagation();
                handleCloseTab(tab.id);
              }}
              title="Đóng tab"
            >
              ×
            </button>
          </div>
        ))}
      </div>

      {/* ── Content Area ─── READ ONLY ────────────────────── */}
      <div className="data-viewer-content">
        {fetchStatus === "loading" ? (
          <div className="data-viewer-loading">
            <div className="data-viewer-loading-spinner" />
            <p>Đang tải dữ liệu...</p>
          </div>
        ) : fetchStatus === "error" ? (
          <div className="data-viewer-error">
            <div className="data-viewer-error-card">
              <div className="data-viewer-error-visual">
                <div className="dv-error-ring dv-error-ring--1" />
                <div className="dv-error-ring dv-error-ring--2" />
                <div className="dv-error-emoji">{isRecoverable ? "⏳" : "📭"}</div>
              </div>
              <h3 className="data-viewer-error-title">
                {isRecoverable ? "Lỗi kết nối" : "Dữ liệu đã hết hạn"}
              </h3>
              <p className="data-viewer-error-msg">{errorMessage}</p>
              <div className="data-viewer-error-actions">
                {isRecoverable ? (
                  <button className="data-viewer-retry-btn" onClick={handleRetry}>
                    <span className="dv-btn-icon">↻</span> Thử lại
                  </button>
                ) : (
                  <button
                    className="data-viewer-retry-btn"
                    onClick={() => useAppStore.getState().setActiveView("upload")}
                  >
                    <span className="dv-btn-icon">☁️</span> Upload lại
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : activeData ? (
          activeFile?.type === ".docx" || activeFile?.type === ".pptx" ? (
            /* Word/PowerPoint: Text content — READ ONLY */
            <div className="data-viewer-text">
              <textarea
                className="data-viewer-textarea"
                defaultValue={activeData.contextText || "Không có nội dung văn bản."}
                readOnly
              />
            </div>
          ) : (
            /* Excel/CSV: Table — READ ONLY, no editing */
            <div className="data-viewer-table-wrapper" ref={(el) => {
              if (el && activeTabId && _scrollPositions[activeTabId] !== undefined) {
                requestAnimationFrame(() => {
                  el.scrollTop = _scrollPositions[activeTabId];
                });
              }
            }} onScroll={(e) => {
              if (activeTabId) {
                _scrollPositions[activeTabId] = e.currentTarget.scrollTop;
              }
            }}>
              <table className="data-viewer-table">
                <thead>
                  <tr>
                    <th className="data-viewer-th data-viewer-row-num">#</th>
                    {activeData.columns.map((col) => (
                      <th key={col} className="data-viewer-th">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {activeData.rows.map((row, i) => (
                    <tr key={i} className="data-viewer-row">
                      <td className="data-viewer-td data-viewer-row-num">{i + 1}</td>
                      {activeData.columns.map((col) => (
                        <td
                          key={col}
                          className="data-viewer-td"
                        >
                          {row[col] != null ? String(row[col]) : ""}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {activeData.totalRows > activeData.rows.length && (
                <div className="data-viewer-truncated">
                  Hiển thị {activeData.rows.length} / {activeData.totalRows} hàng
                </div>
              )}
            </div>
          )
        ) : (
          <div className="data-viewer-loading">
            <div className="data-viewer-loading-spinner" />
            <p>Đang tải dữ liệu...</p>
          </div>
        )}
      </div>
    </div>
  );
}
