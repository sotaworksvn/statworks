"use client";

import { SchoolMatch } from "@/lib/types";
import { useTranslations } from "next-intl";

interface Props {
  match: SchoolMatch;
}

const LEVEL_CONFIG = {
  dream: {
    label: "Mơ ước",
    labelEn: "Dream",
    bg: "bg-purple-50",
    border: "border-purple-200",
    badge: "bg-purple-100 text-purple-700",
    bar: "bg-purple-500",
    icon: "🌟",
  },
  target: {
    label: "Phù hợp",
    labelEn: "Target",
    bg: "bg-blue-50",
    border: "border-blue-200",
    badge: "bg-blue-100 text-blue-700",
    bar: "bg-blue-500",
    icon: "🎯",
  },
  safety: {
    label: "An toàn",
    labelEn: "Safety",
    bg: "bg-green-50",
    border: "border-green-200",
    badge: "bg-green-100 text-green-700",
    bar: "bg-green-500",
    icon: "✅",
  },
} as const;

export function SchoolCard({ match }: Props) {
  const config = LEVEL_CONFIG[match.match_level];

  return (
    <div className={`rounded-xl border ${config.border} ${config.bg} p-4 space-y-3 hover:shadow-md transition-shadow`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{config.icon}</span>
            <span className={`text-xs font-semibold rounded-full px-2 py-0.5 ${config.badge}`}>
              {config.label}
            </span>
            <span className="text-xs text-gray-400">{match.country}</span>
          </div>
          <h3 className="font-semibold text-[#1A1A2E] text-sm leading-tight">
            {match.school_name}
          </h3>
        </div>
        <div className="text-right shrink-0">
          <div className="text-2xl font-bold text-[#2D3561]">{match.match_score}%</div>
          <div className="text-xs text-gray-400">khả năng đỗ</div>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-200 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full ${config.bar} transition-all duration-700`}
          style={{ width: `${match.match_score}%` }}
        />
      </div>

      {/* Strengths & Weaknesses */}
      {(match.strengths.length > 0 || match.weaknesses.length > 0) && (
        <div className="grid grid-cols-2 gap-2">
          {match.strengths.length > 0 && (
            <div>
              <div className="text-xs font-medium text-green-700 mb-1">✓ Điểm mạnh</div>
              <ul className="space-y-0.5">
                {match.strengths.slice(0, 2).map((s, i) => (
                  <li key={i} className="text-xs text-gray-600 leading-snug">
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {match.weaknesses.length > 0 && (
            <div>
              <div className="text-xs font-medium text-orange-600 mb-1">⚠ Cải thiện</div>
              <ul className="space-y-0.5">
                {match.weaknesses.slice(0, 2).map((w, i) => (
                  <li key={i} className="text-xs text-gray-600 leading-snug">
                    {w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
