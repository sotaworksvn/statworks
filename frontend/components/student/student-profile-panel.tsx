"use client";

import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";

// ── Types ──────────────────────────────────────────────────────────────────

interface Opportunity {
  school_name: string;
  country?: string;
  program?: string;
  scholarship_name?: string;
  amount_usd?: number;
  deadline?: string;
  gpa_requirement?: number;
  ielts_requirement?: number;
  toefl_requirement?: number;
  sat_requirement?: number;
  match_score?: number;
  match_level?: "dream" | "target" | "safety";
  match_reasons?: string[];
  apply_url?: string;
}

interface SimulateCriterion {
  key: string;
  label: string;
  type: "numeric" | "award_rank" | "text";
  min?: number;
  max?: number;
  step?: number;
  current?: number;
  unit?: string;
  options?: Array<{ value: number; label: string }>;
  placeholder?: string;
  description?: string;
}

interface RoadmapMilestone {
  month: string;
  phase: string;
  milestones: string[];
  priority: "high" | "medium" | "low";
  notes?: string;
}

export interface StudentProfileResult {
  result_type: "student_profile_analysis";
  summary?: string;
  recommendation?: string;
  student_tier?: string;
  student_profile_full?: {
    name?: string;
    school?: string;
    city?: string;
    dob?: string;
    gpa_10?: number;
    gpa_4?: number;
    toefl?: number;
    ielts?: number;
    sat?: number;
    target_major?: string;
    target_country?: string;
    target_intake?: string;
    overall_tier?: string;
    tier_description?: string;
    strengths?: string[];
    gaps?: string[];
    strongest_subjects?: string[];
    weakest_subjects?: string[];
    awards?: Array<{ name: string; level: string; year: string; description?: string }>;
    extracurriculars?: Array<{ name: string; role: string; org?: string; period?: string; description?: string }>;
    soft_skill_certs?: Array<{ name: string; org?: string; year?: string }>;
    ap_courses?: Array<{ name: string; score: number }>;
    composite_score?: number;
  };
  capability_analysis?: {
    gpa_trend?: Array<{ semester: string; average_gpa: number }>;
    subject_stats?: Array<{
      subject: string; mean: number; std: number; min: number; max: number;
      trend: string; n_semesters: number;
    }>;
    strength_breakdown?: Record<string, number>;
    key_insights?: string[];
    capability_level?: string;
    strengths?: string[];
    gaps?: string[];
    composite_score?: number;
  };
  scholarship_opportunities?: Opportunity[];
  roadmap?: RoadmapMilestone[];
  simulate_criteria?: SimulateCriterion[];
}

interface Props {
  insight: StudentProfileResult;
  fileId?: string;
}

// ── Color helpers ──────────────────────────────────────────────────────────

const MATCH_COLORS = {
  dream: { bg: "bg-purple-50", text: "text-purple-700", badge: "bg-purple-600 text-white" },
  target: { bg: "bg-blue-50", text: "text-blue-700", badge: "bg-blue-500 text-white" },
  safety: { bg: "bg-green-50", text: "text-green-700", badge: "bg-green-500 text-white" },
};

const PHASE_COLORS: Record<string, string> = {
  prep: "bg-blue-100 text-blue-700",
  test: "bg-yellow-100 text-yellow-700",
  apply: "bg-orange-100 text-orange-700",
  wait: "bg-gray-100 text-gray-600",
  improve: "bg-green-100 text-green-700",
};

const PRIORITY_DOT: Record<string, string> = {
  high: "bg-red-500",
  medium: "bg-amber-400",
  low: "bg-green-400",
};

// ── Simulation helper (local, no external call) ────────────────────────────

function computeSimulationLocal(
  criterion: SimulateCriterion,
  newValue: number,
  profile: StudentProfileResult["student_profile_full"],
  opportunity: Opportunity | undefined
): { current: number; improved: number; delta: number; analysis: string } {
  const baseScore = opportunity?.match_score ?? 75;
  const current = Math.round(baseScore);

  let delta = 0;
  const cur = criterion.current ?? 0;
  const range = (criterion.max ?? 10) - (criterion.min ?? 0);

  if (criterion.type === "numeric" && range > 0) {
    const improvement = (newValue - cur) / range;
    delta = Math.round(improvement * 18);
  } else if (criterion.type === "award_rank") {
    delta = Math.round(newValue * 3);
  } else {
    delta = 5;
  }

  const improved = Math.min(100, Math.max(0, current + delta));

  let analysis = "";
  if (improved >= 90) analysis = "Đạt ngưỡng học bổng xuất sắc — khả năng cao được nhận.";
  else if (improved >= 80) analysis = "Hồ sơ rất cạnh tranh — khả năng nhận học bổng cao.";
  else if (improved >= 70) analysis = "Hồ sơ cạnh tranh tốt — nên nộp đơn sớm.";
  else if (delta > 0) analysis = "Cải thiện đáng kể so với hồ sơ hiện tại.";
  else analysis = "Tiêu chí này không thay đổi nhiều — cần cải thiện yếu tố khác.";

  return { current, improved, delta, analysis };
}

// ── Main Component ─────────────────────────────────────────────────────────

export function StudentProfilePanel({ insight, fileId }: Props) {
  const [activeSection, setActiveSection] = useState<
    "capability" | "opportunities" | "roadmap" | "simulate"
  >("capability");
  const [oppFilter, setOppFilter] = useState<"all" | "dream" | "target" | "safety">("all");
  const [simSchool, setSimSchool] = useState("");
  const [simCriterionKey, setSimCriterionKey] = useState("");
  const [simValue, setSimValue] = useState<number>(0);
  const [simText, setSimText] = useState("");
  const [simResult, setSimResult] = useState<{
    current: number; improved: number; delta: number; analysis: string;
  } | null>(null);

  const profile = insight.student_profile_full ?? {};
  const capability = insight.capability_analysis ?? {};
  const opportunities = insight.scholarship_opportunities ?? [];
  const roadmap = insight.roadmap ?? [];
  const criteria = insight.simulate_criteria ?? [];

  const filteredOpps = useMemo(
    () => oppFilter === "all" ? opportunities : opportunities.filter(o => o.match_level === oppFilter),
    [opportunities, oppFilter]
  );

  const oppCounts = useMemo(() => ({
    all: opportunities.length,
    dream: opportunities.filter(o => o.match_level === "dream").length,
    target: opportunities.filter(o => o.match_level === "target").length,
    safety: opportunities.filter(o => o.match_level === "safety").length,
  }), [opportunities]);

  const currentCriterion = criteria.find(c => c.key === simCriterionKey);
  const selectedOpportunity = opportunities.find(o => o.school_name === simSchool);

  // Strength breakdown as sorted table rows
  const strengthRows = useMemo(() => {
    const sb = capability.strength_breakdown ?? {};
    return Object.entries(sb)
      .sort(([, a], [, b]) => b - a)
      .map(([key, value]) => ({ area: key, score: value }));
  }, [capability.strength_breakdown]);

  const runSimulation = () => {
    if (!simSchool || !simCriterionKey || !currentCriterion) return;
    const result = computeSimulationLocal(currentCriterion, simValue, profile, selectedOpportunity);
    setSimResult(result);
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="flex flex-col h-full overflow-y-auto space-y-4 pb-8">

      {/* ── Hero Header ── */}
      <motion.div
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl bg-gradient-to-br from-[#2D3561] via-[#3a4578] to-[#1a2040] p-5 text-white relative overflow-hidden"
      >
        <div className="absolute inset-0 opacity-10"
          style={{ backgroundImage: "radial-gradient(circle at 80% 20%, #6366F1 0%, transparent 60%)" }} />
        <div className="relative z-10">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h2 className="text-2xl font-extrabold leading-tight tracking-tight">
                {profile.name && profile.name !== "Học sinh" ? profile.name : "Học sinh"}
              </h2>
              <p className="text-white/70 text-sm mt-1 flex flex-wrap gap-x-2 gap-y-0.5">
                {[
                  profile.school,
                  profile.city,
                  profile.target_major || null,
                  profile.target_country ? `tại ${profile.target_country}` : null,
                  profile.target_intake || null,
                ].filter(Boolean).map((item, i, arr) => (
                  <span key={i}>
                    {item}{i < arr.length - 1 && <span className="opacity-50 ml-2">·</span>}
                  </span>
                ))}
              </p>
            </div>
            <div className={`shrink-0 self-start rounded-full px-3 py-1 text-xs font-bold whitespace-nowrap ${
              (insight.student_tier ?? profile.overall_tier ?? "").includes("Top 1")
                ? "bg-yellow-400 text-yellow-900"
                : (insight.student_tier ?? profile.overall_tier ?? "").includes("Top 5")
                ? "bg-blue-400 text-white"
                : "bg-white/20 text-white"
            }`}>
              {insight.student_tier ?? profile.overall_tier ?? ""}
            </div>
          </div>

          {/* Profile chips */}
          <div className="flex flex-wrap gap-2 mt-3">
            {profile.gpa_10 && (
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs">GPA {profile.gpa_10}/10 ({profile.gpa_4}/4.0)</span>
            )}
            {profile.sat && (
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs">SAT {profile.sat}</span>
            )}
            {profile.toefl && (
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs">TOEFL {profile.toefl}</span>
            )}
            {profile.ielts && (
              <span className="rounded-full bg-white/15 px-3 py-1 text-xs">IELTS {profile.ielts}</span>
            )}
          </div>

          {/* Tier description */}
          {profile.tier_description && (
            <p className="text-white/60 text-xs mt-2">{profile.tier_description}</p>
          )}
        </div>
      </motion.div>

      {/* ── Section Tabs ── */}
      <div className="flex gap-1 bg-gray-100 rounded-xl p-1">
        {([
          { key: "capability", label: "📊 Năng lực" },
          { key: "opportunities", label: `🎓 Cơ hội (${opportunities.length})` },
          { key: "roadmap", label: "🗓 Lộ trình" },
          { key: "simulate", label: "🎮 Simulate" },
        ] as const).map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveSection(tab.key)}
            className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${
              activeSection === tab.key
                ? "bg-white text-[#2D3561] shadow-sm"
                : "text-gray-500 hover:text-[#2D3561]"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════════════════ */}
      {/* SECTION 1: CAPABILITY ───────────────────────────────────────────── */}
      {/* ══════════════════════════════════════════════════════════════════════ */}
      <AnimatePresence mode="wait">
        {activeSection === "capability" && (
          <motion.div
            key="capability"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="space-y-4"
          >
            {/* Key Insights */}
            {capability.key_insights && capability.key_insights.length > 0 && (
              <div className="rounded-xl bg-[#F5F7FF] border border-[#2D3561]/10 p-4">
                <h3 className="text-xs font-bold text-[#2D3561] uppercase tracking-wider mb-3">
                  💡 Insight Năng lực
                </h3>
                <ul className="space-y-2">
                  {capability.key_insights.map((ins, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                      <span className="text-[#6366F1] mt-0.5 shrink-0">•</span>
                      {ins}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Strength Breakdown TABLE (replaces chart) */}
            {strengthRows.length > 0 && (
              <div className="rounded-xl border border-gray-100 p-4 overflow-x-auto">
                <h3 className="text-xs font-bold text-[#2D3561] uppercase tracking-wider mb-3">
                  📊 Bảng đánh giá năng lực tổng hợp
                </h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="py-2 px-2 text-left font-semibold text-[#2D3561]">Lĩnh vực</th>
                      <th className="py-2 px-2 text-right font-semibold text-[#2D3561]">Điểm / 10</th>
                      <th className="py-2 px-2 text-left font-semibold text-[#2D3561]">Mức độ</th>
                      <th className="py-2 px-2 text-left font-semibold text-[#2D3561] w-48">Tiến trình</th>
                    </tr>
                  </thead>
                  <tbody>
                    {strengthRows.map(({ area, score }) => (
                      <tr key={area} className="border-b border-gray-50 hover:bg-[#F5F5F7]/60 transition-colors">
                        <td className="py-2 px-2 font-medium text-[#2D3561]">{area}</td>
                        <td className={`py-2 px-2 text-right font-bold ${
                          score >= 8.5 ? "text-green-600" : score >= 7 ? "text-blue-600" : score >= 5 ? "text-amber-600" : "text-gray-400"
                        }`}>
                          {score.toFixed(2)}
                        </td>
                        <td className="py-2 px-2">
                          <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${
                            score >= 8.5 ? "bg-green-100 text-green-700" :
                            score >= 7 ? "bg-blue-100 text-blue-700" :
                            score >= 5 ? "bg-amber-100 text-amber-700" :
                            "bg-gray-100 text-gray-500"
                          }`}>
                            {score >= 9 ? "Xuất sắc" : score >= 8 ? "Giỏi" : score >= 7 ? "Khá" : score >= 5 ? "TB" : "Yếu"}
                          </span>
                        </td>
                        <td className="py-2 px-2">
                          <div className="h-2 bg-gray-100 rounded-full overflow-hidden w-36">
                            <div
                              className={`h-full rounded-full transition-all ${
                                score >= 8.5 ? "bg-green-500" : score >= 7 ? "bg-blue-500" : score >= 5 ? "bg-amber-400" : "bg-gray-300"
                              }`}
                              style={{ width: `${(score / 10) * 100}%` }}
                            />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* GPA Trend TABLE (replaces line chart) */}
            {(capability.gpa_trend ?? []).length > 0 && (
              <div className="rounded-xl border border-gray-100 p-4 overflow-x-auto">
                <h3 className="text-xs font-bold text-[#2D3561] uppercase tracking-wider mb-3">
                  📈 Xu hướng GPA qua các học kỳ
                </h3>
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100">
                      <th className="py-2 px-2 text-left font-semibold text-[#2D3561]">Học kỳ</th>
                      <th className="py-2 px-2 text-right font-semibold text-[#2D3561]">GPA TB</th>
                      <th className="py-2 px-2 text-left font-semibold text-[#2D3561] w-48">Tiến trình</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(capability.gpa_trend ?? []).map((row, i, arr) => {
                      const prev = arr[i - 1]?.average_gpa;
                      const trend = prev == null ? "→" : row.average_gpa > prev + 0.05 ? "↑" : row.average_gpa < prev - 0.05 ? "↓" : "→";
                      return (
                        <tr key={row.semester} className="border-b border-gray-50 hover:bg-[#F5F5F7]/60 transition-colors">
                          <td className="py-2 px-2 font-medium text-[#2D3561]">{row.semester}</td>
                          <td className={`py-2 px-2 text-right font-bold ${
                            row.average_gpa >= 9 ? "text-green-600" : row.average_gpa >= 8 ? "text-blue-600" : "text-amber-600"
                          }`}>
                            {row.average_gpa} <span className={trend === "↑" ? "text-green-500" : trend === "↓" ? "text-red-500" : "text-gray-400"}>{trend}</span>
                          </td>
                          <td className="py-2 px-2">
                            <div className="h-2 bg-gray-100 rounded-full overflow-hidden w-36">
                              <div
                                className="h-full bg-[#6366F1] rounded-full transition-all"
                                style={{ width: `${(row.average_gpa / 10) * 100}%` }}
                              />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            {/* Subject Stats Table */}
            {capability.subject_stats && capability.subject_stats.length > 0 && (
              <div className="rounded-xl border border-gray-100 p-4 overflow-x-auto">
                <h3 className="text-xs font-bold text-[#2D3561] uppercase tracking-wider mb-3">
                  📋 Bảng thống kê môn học (SPSS-style)
                </h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100">
                      {["Môn học", "TB", "Độ lệch", "Min", "Max", "Xu hướng"].map(h => (
                        <th key={h} className={`py-2 px-2 font-semibold text-[#2D3561] ${h === "Môn học" ? "text-left" : "text-right"}`}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {capability.subject_stats.map((s) => (
                      <tr key={s.subject} className="border-b border-gray-50 hover:bg-[#F5F5F7]/60 transition-colors">
                        <td className="py-2 px-2 font-medium text-[#2D3561]">{s.subject}</td>
                        <td className={`py-2 px-2 text-right font-bold ${s.mean >= 9 ? "text-green-600" : s.mean >= 8 ? "text-blue-600" : "text-gray-600"}`}>
                          {s.mean}
                        </td>
                        <td className="py-2 px-2 text-right text-gray-400">{s.std}</td>
                        <td className="py-2 px-2 text-right text-gray-500">{s.min}</td>
                        <td className="py-2 px-2 text-right text-gray-500">{s.max}</td>
                        <td className={`py-2 px-2 text-right font-bold ${
                          s.trend === "↑" ? "text-green-500" : s.trend === "↓" ? "text-red-500" : "text-gray-400"
                        }`}>{s.trend}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-gray-400 mt-2">{capability.subject_stats.length} môn · {profile.awards?.length ?? 0} giải thưởng</p>
              </div>
            )}

            {/* Activities & Awards Tables */}
            {(profile.awards && profile.awards.length > 0) && (
              <div className="rounded-xl border border-gray-100 p-4 overflow-x-auto">
                <h3 className="text-xs font-bold text-[#2D3561] uppercase tracking-wider mb-3">
                  🏆 Giải thưởng học thuật ({profile.awards.length})
                </h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100">
                      {["Giải thưởng", "Cấp độ", "Năm", "Mô tả"].map(h => (
                        <th key={h} className="py-2 px-2 font-semibold text-[#2D3561] text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {profile.awards.map((a, i) => (
                      <tr key={i} className="border-b border-gray-50 hover:bg-[#F5F5F7]/60 transition-colors">
                        <td className="py-2 px-2 font-medium text-[#2D3561] max-w-[160px]">{a.name}</td>
                        <td className="py-2 px-2">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            a.level?.toLowerCase().includes("quốc tế") ? "bg-yellow-100 text-yellow-700" :
                            a.level?.toLowerCase().includes("quốc gia") ? "bg-blue-100 text-blue-700" :
                            a.level?.toLowerCase().includes("thành phố") ? "bg-green-100 text-green-700" :
                            "bg-gray-100 text-gray-600"
                          }`}>
                            {a.level}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-gray-500">{a.year}</td>
                        <td className="py-2 px-2 text-gray-500 max-w-[180px] truncate" title={(a as any).description}>{(a as any).description ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {(profile.extracurriculars && profile.extracurriculars.length > 0) && (
              <div className="rounded-xl border border-gray-100 p-4 overflow-x-auto">
                <h3 className="text-xs font-bold text-[#2D3561] uppercase tracking-wider mb-3">
                  🎯 Hoạt động ngoại khoá ({profile.extracurriculars.length})
                </h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100">
                      {["Hoạt động", "Vai trò", "Tổ chức", "Thời gian"].map(h => (
                        <th key={h} className="py-2 px-2 font-semibold text-[#2D3561] text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {profile.extracurriculars.map((ec, i) => (
                      <tr key={i} className="border-b border-gray-50 hover:bg-[#F5F5F7]/60 transition-colors">
                        <td className="py-2 px-2 font-medium text-[#2D3561] max-w-[140px]">{ec.name}</td>
                        <td className="py-2 px-2">
                          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                            ec.role?.toLowerCase().includes("trưởng") || ec.role?.toLowerCase().includes("chủ")
                              ? "bg-purple-100 text-purple-700"
                              : "bg-gray-100 text-gray-600"
                          }`}>
                            {ec.role}
                          </span>
                        </td>
                        <td className="py-2 px-2 text-gray-500">{(ec as any).org ?? "—"}</td>
                        <td className="py-2 px-2 text-gray-500">{(ec as any).period ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Strengths & Gaps */}
            {(capability.strengths?.length || capability.gaps?.length) && (
              <div className="grid grid-cols-1 gap-3">
                {capability.strengths && capability.strengths.length > 0 && (
                  <div className="rounded-xl bg-green-50 border border-green-100 p-4">
                    <h4 className="text-xs font-bold text-green-700 uppercase tracking-wider mb-2">✅ Điểm mạnh</h4>
                    <ul className="space-y-1">
                      {capability.strengths.map((s, i) => (
                        <li key={i} className="text-xs text-green-800">• {s}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {capability.gaps && capability.gaps.length > 0 && (
                  <div className="rounded-xl bg-amber-50 border border-amber-100 p-4">
                    <h4 className="text-xs font-bold text-amber-700 uppercase tracking-wider mb-2">⚠️ Cần cải thiện</h4>
                    <ul className="space-y-1">
                      {capability.gaps.map((g, i) => (
                        <li key={i} className="text-xs text-amber-800">• {g}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}
          </motion.div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 2: SCHOLARSHIP OPPORTUNITIES ─────────────────────────────── */}
        {/* ══════════════════════════════════════════════════════════════════════ */}
        {activeSection === "opportunities" && (
          <motion.div
            key="opportunities"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="space-y-4"
          >
            {/* Filter tabs */}
            <div className="flex gap-2">
              {(["all", "dream", "target", "safety"] as const).map(f => (
                <button
                  key={f}
                  onClick={() => setOppFilter(f)}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-colors ${
                    oppFilter === f ? "bg-[#2D3561] text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {f === "all" ? "Tất cả" : f === "dream" ? "Mơ ước" : f === "target" ? "Phù hợp" : "An toàn"}
                  <span className="ml-1 opacity-70">({oppCounts[f]})</span>
                </button>
              ))}
            </div>

            {/* Scholarship table */}
            {filteredOpps.length > 0 ? (
              <div className="rounded-xl border border-gray-100 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-[#F5F7FF] border-b border-gray-100">
                      {["Trường", "Học bổng", "Số tiền", "Deadline", "GPA yêu cầu", "Match", ""].map(h => (
                        <th key={h} className="py-2.5 px-3 font-semibold text-[#2D3561] text-left">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredOpps.map((opp, i) => {
                      const mc = MATCH_COLORS[opp.match_level ?? "target"];
                      return (
                        <tr key={i} className="border-b border-gray-50 hover:bg-[#F5F5F7]/60 transition-colors">
                          <td className="py-2.5 px-3">
                            <div className="font-medium text-[#2D3561] max-w-[120px] truncate" title={opp.school_name}>
                              {opp.school_name}
                            </div>
                            <div className="text-gray-400">{opp.country}</div>
                          </td>
                          <td className="py-2.5 px-3 max-w-[120px]">
                            <div className="text-gray-700 truncate" title={opp.scholarship_name}>
                              {opp.scholarship_name ?? opp.program ?? "—"}
                            </div>
                          </td>
                          <td className="py-2.5 px-3 text-green-700 font-semibold whitespace-nowrap">
                            {opp.amount_usd ? `$${(opp.amount_usd / 1000).toFixed(0)}K/yr` : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-gray-600 whitespace-nowrap">
                            {opp.deadline ?? "—"}
                          </td>
                          <td className="py-2.5 px-3 text-gray-600 whitespace-nowrap">
                            {opp.gpa_requirement ? `≥ ${opp.gpa_requirement}/4.0` : "—"}
                          </td>
                          <td className="py-2.5 px-3">
                            <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-bold text-xs ${mc.badge}`}>
                              {opp.match_score?.toFixed(0) ?? "—"}%
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            {opp.apply_url && (
                              <a
                                href={opp.apply_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-blue-500 hover:underline text-xs"
                              >
                                Apply →
                              </a>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-center py-10 text-gray-400 text-sm">
                Không có cơ hội nào ở mức lọc này
              </div>
            )}

            {/* Match reasons for top opportunity */}
            {filteredOpps[0]?.match_reasons && (
              <div className="rounded-xl bg-[#F5F7FF] border border-[#2D3561]/10 p-4">
                <h4 className="text-xs font-bold text-[#2D3561] mb-2">
                  Lý do phù hợp: {filteredOpps[0].school_name}
                </h4>
                <ul className="space-y-1">
                  {filteredOpps[0].match_reasons.map((r, i) => (
                    <li key={i} className="text-xs text-gray-600">✓ {r}</li>
                  ))}
                </ul>
              </div>
            )}
          </motion.div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 3: ROADMAP ──────────────────────────────────────────────── */}
        {/* ══════════════════════════════════════════════════════════════════════ */}
        {activeSection === "roadmap" && (
          <motion.div
            key="roadmap"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="space-y-3"
          >
            <p className="text-xs text-gray-500 px-1">
              Lộ trình cá nhân hoá cho <strong>{profile.name && profile.name !== "Học sinh" ? profile.name : "học sinh"}</strong>
              {profile.target_major ? ` — ${profile.target_major}` : ""}
              {profile.target_country ? ` tại ${profile.target_country}` : ""}
            </p>

            {roadmap.length > 0 ? roadmap.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                className="rounded-xl border border-gray-100 p-4"
              >
                <div className="flex items-center justify-between mb-2 gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`w-2 h-2 rounded-full shrink-0 ${PRIORITY_DOT[m.priority] ?? "bg-gray-300"}`} />
                    <span className="font-semibold text-[#2D3561] text-sm">{m.month}</span>
                  </div>
                  <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${PHASE_COLORS[m.phase] ?? "bg-gray-100 text-gray-600"}`}>
                    {m.phase}
                  </span>
                </div>
                <ul className="space-y-1.5 mb-2">
                  {m.milestones.map((ms, j) => (
                    <li key={j} className="text-xs text-gray-700 flex items-start gap-2">
                      <span className="text-[#6366F1] shrink-0 mt-0.5">→</span>
                      {ms}
                    </li>
                  ))}
                </ul>
                {m.notes && (
                  <p className="text-xs text-gray-400 italic mt-1">{m.notes}</p>
                )}
              </motion.div>
            )) : (
              <div className="text-center py-10 text-gray-400 text-sm">
                Chưa có lộ trình — vui lòng đợi hệ thống tạo lộ trình.
              </div>
            )}
          </motion.div>
        )}

        {/* ══════════════════════════════════════════════════════════════════════ */}
        {/* SECTION 4: SIMULATE ─────────────────────────────────────────────── */}
        {/* ══════════════════════════════════════════════════════════════════════ */}
        {activeSection === "simulate" && (
          <motion.div
            key="simulate"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="space-y-4"
          >
            <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-5">
              <h3 className="font-semibold text-[#2D3561] text-base">🎮 Mô phỏng cải thiện hồ sơ</h3>

              {/* Step 1: School selector */}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1.5 block">
                  1. Chọn trường cần simulate
                </label>
                <select
                  className="w-full rounded-lg border border-gray-200 bg-white p-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#2D3561]/30"
                  value={simSchool}
                  onChange={e => { setSimSchool(e.target.value); setSimResult(null); }}
                >
                  <option value="">-- Chọn trường từ kết quả tìm kiếm --</option>
                  {opportunities.slice(0, 15).map((o, i) => (
                    <option key={i} value={o.school_name}>
                      {o.school_name} ({o.match_level === "dream" ? "Mơ ước" : o.match_level === "target" ? "Phù hợp" : "An toàn"} · {o.match_score?.toFixed(0)}%)
                    </option>
                  ))}
                </select>
              </div>

              {/* Step 2: Criteria selector */}
              <div>
                <label className="text-xs font-medium text-gray-500 mb-1.5 block">
                  2. Chọn tiêu chí cần cải thiện
                </label>
                <div className="flex flex-wrap gap-2">
                  {criteria.map(c => (
                    <button
                      key={c.key}
                      onClick={() => {
                        setSimCriterionKey(c.key);
                        setSimValue(c.current ?? c.min ?? 0);
                        setSimText("");
                        setSimResult(null);
                      }}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        simCriterionKey === c.key
                          ? "bg-[#6366F1] text-white"
                          : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                      }`}
                    >
                      {c.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Step 3: Dynamic input */}
              {currentCriterion && (
                <div className="rounded-xl bg-gray-50 p-4 space-y-3">
                  {currentCriterion.type === "numeric" && (
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-2 block">
                        {currentCriterion.label}:{" "}
                        <span className="font-bold text-[#6366F1]">
                          {simValue}{currentCriterion.unit}
                        </span>
                        <span className="text-gray-400 ml-2">(hiện tại: {currentCriterion.current}{currentCriterion.unit})</span>
                      </label>
                      <input
                        type="range"
                        className="w-full accent-[#6366F1]"
                        min={currentCriterion.min}
                        max={currentCriterion.max}
                        step={currentCriterion.step}
                        value={simValue}
                        onChange={e => { setSimValue(parseFloat(e.target.value)); setSimResult(null); }}
                      />
                      <div className="flex justify-between text-xs text-gray-400 mt-0.5">
                        <span>{currentCriterion.min}</span>
                        <span>{currentCriterion.max}</span>
                      </div>
                    </div>
                  )}

                  {currentCriterion.type === "award_rank" && currentCriterion.options && (
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-2 block">
                        {currentCriterion.label}
                      </label>
                      <div className="flex flex-col gap-1">
                        {currentCriterion.options.map(opt => (
                          <button
                            key={opt.value}
                            onClick={() => { setSimValue(opt.value); setSimResult(null); }}
                            className={`text-left px-3 py-2 rounded-lg text-xs transition-colors ${
                              simValue === opt.value
                                ? "bg-[#6366F1] text-white font-semibold"
                                : "bg-white border border-gray-200 text-gray-700 hover:bg-gray-50"
                            }`}
                          >
                            {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {currentCriterion.type === "text" && (
                    <div>
                      <label className="text-xs font-medium text-gray-600 mb-2 block">
                        {currentCriterion.description}
                      </label>
                      <textarea
                        className="w-full rounded-lg border border-gray-200 p-3 text-sm focus:outline-none focus:ring-2 focus:ring-[#6366F1]/30 resize-none"
                        rows={3}
                        placeholder={currentCriterion.placeholder}
                        value={simText}
                        onChange={e => { setSimText(e.target.value); setSimResult(null); }}
                      />
                      <p className="text-xs text-gray-400 mt-1">AI sẽ phân tích và tính toán tác động lên hồ sơ.</p>
                    </div>
                  )}
                </div>
              )}

              {/* Run button */}
              <button
                onClick={runSimulation}
                disabled={!simSchool || !simCriterionKey || (currentCriterion?.type === "text" && !simText.trim())}
                className="w-full rounded-lg bg-[#2D3561] py-2.5 text-white text-sm font-semibold hover:bg-[#3a4578] active:scale-[0.99] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Xem kết quả mô phỏng
              </button>

              {/* Simulation result */}
              {simResult && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.97 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="rounded-xl bg-gradient-to-br from-[#6366F1]/10 to-[#6366F1]/5 border border-[#6366F1]/20 p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Khả năng hiện tại (với {simSchool})</span>
                    <span className="font-bold text-gray-700">{simResult.current}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Sau khi cải thiện</span>
                    <span className="text-2xl font-bold text-[#6366F1]">{simResult.improved}%</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600">Thay đổi</span>
                    <span className={`font-bold text-base ${simResult.delta >= 0 ? "text-green-600" : "text-red-500"}`}>
                      {simResult.delta >= 0 ? "+" : ""}{simResult.delta}%
                    </span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-gray-400">
                      <span>Trước</span><span>Sau</span>
                    </div>
                    <div className="h-3 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-[#6366F1] to-[#22C55E] rounded-full transition-all duration-700"
                        style={{ width: `${simResult.improved}%` }}
                      />
                    </div>
                  </div>
                  {simResult.analysis && (
                    <p className="text-sm text-[#2D3561] font-medium">📈 {simResult.analysis}</p>
                  )}
                </motion.div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
