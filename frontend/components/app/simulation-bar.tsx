"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { SimulationPanel } from "@/components/scholarship/simulation-panel";

/**
 * SimulationBar — collapsible bottom panel in the chat view.
 * Shows only when a scholarship_prediction result is available.
 */
export function SimulationBar() {
  const { insight } = useAppStore();
  const [open, setOpen] = useState(false);

  // Only render for scholarship prediction results with school matches
  if (
    !insight ||
    insight.result_type !== "scholarship_prediction" ||
    !insight.school_matches?.length
  ) {
    return null;
  }

  return (
    <div
      className="border-t border-gray-100 bg-white transition-all duration-300"
      style={{ flexShrink: 0 }}
    >
      {/* Toggle handle */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-6 py-3 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-base">🎮</span>
          <span className="text-sm font-semibold text-[#2D3561]">
            Mô Phỏng Cải Thiện Hồ Sơ
          </span>
          <span className="rounded-full bg-[#FF6B4A]/10 px-2 py-0.5 text-xs font-medium text-[#FF6B4A]">
            {insight.school_matches.length} trường
          </span>
        </div>
        <svg
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`text-gray-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        >
          <polyline points="18 15 12 9 6 15" />
        </svg>
      </button>

      {/* Collapsible body */}
      {open && (
        <div className="border-t border-gray-100 px-6 py-4 max-h-[420px] overflow-y-auto">
          <SimulationPanel />
        </div>
      )}
    </div>
  );
}
