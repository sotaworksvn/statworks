"use client";

import { InsightResult, SchoolMatch } from "@/lib/types";
import { SchoolCard } from "./school-card";
import { useState } from "react";

interface Props {
  insight: InsightResult;
}

type FilterLevel = "all" | "dream" | "target" | "safety";

const LEVEL_LABELS: Record<FilterLevel, string> = {
  all: "Tất cả",
  dream: "Mơ ước",
  target: "Phù hợp",
  safety: "An toàn",
};

export function ScholarshipResults({ insight }: Props) {
  const [filter, setFilter] = useState<FilterLevel>("all");
  const matches = insight.school_matches ?? [];

  const filtered = filter === "all" ? matches : matches.filter((m) => m.match_level === filter);

  const counts = {
    all: matches.length,
    dream: matches.filter((m) => m.match_level === "dream").length,
    target: matches.filter((m) => m.match_level === "target").length,
    safety: matches.filter((m) => m.match_level === "safety").length,
  };

  // Student profile summary
  const profile = insight.student_profile as Record<string, unknown> | undefined;
  const str = (v: unknown) => (v != null && v !== "" ? String(v) : null);

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="rounded-xl bg-gradient-to-r from-[#2D3561] to-[#3a4578] p-5 text-white">
        <h2 className="text-lg font-semibold mb-1">🎓 Dự Đoán Học Bổng</h2>
        <p className="text-white/80 text-sm">{insight.summary}</p>

        {/* Profile summary chips */}
        {profile && (
          <div className="flex flex-wrap gap-2 mt-3">
            {str(profile.gpa) && (
              <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">
                GPA {str(profile.gpa)}
              </span>
            )}
            {str(profile.sat_score) && (
              <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">
                SAT {str(profile.sat_score)}
              </span>
            )}
            {str(profile.ielts_score) && (
              <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">
                IELTS {str(profile.ielts_score)}
              </span>
            )}
            {str(profile.toefl_score) && (
              <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">
                TOEFL {str(profile.toefl_score)}
              </span>
            )}
            {str(profile.major) && (
              <span className="rounded-full bg-white/20 px-3 py-1 text-xs font-medium">
                {str(profile.major)}
              </span>
            )}
          </div>
        )}
      </div>


      {/* Recommendation */}
      <div className="rounded-xl border border-[#FF6B4A]/20 bg-[#FF6B4A]/5 p-4">
        <div className="flex items-start gap-2">
          <span className="text-lg shrink-0">💡</span>
          <p className="text-sm text-gray-700 leading-relaxed">{insight.recommendation}</p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {(["all", "dream", "target", "safety"] as FilterLevel[]).map((level) => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              filter === level
                ? "bg-[#2D3561] text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            {LEVEL_LABELS[level]}
            <span className="ml-1.5 text-xs opacity-75">({counts[level]})</span>
          </button>
        ))}
      </div>

      {/* School cards grid */}
      <div className="grid grid-cols-1 gap-3">
        {filtered.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">
            Không có trường nào ở mức này
          </div>
        ) : (
          filtered.map((match) => (
            <SchoolCard key={match.school_name} match={match} />
          ))
        )}
      </div>
    </div>
  );
}
