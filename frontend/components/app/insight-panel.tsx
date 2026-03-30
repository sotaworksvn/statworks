"use client";

import { useAppStore } from "@/lib/store";
import { motion, AnimatePresence } from "framer-motion";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Skeleton } from "@/components/ui/skeleton";
import { ScholarshipResults } from "@/components/scholarship/scholarship-results";
import { SimulationPanel } from "@/components/scholarship/simulation-panel";
import { StudentProfilePanel, type StudentProfileResult } from "@/components/student/student-profile-panel";

export function InsightPanel() {
  const { insight, isAnalyzing } = useAppStore();

  // ── Skeleton loading ──
  if (isAnalyzing) {
    return (
      <section className="flex flex-1 flex-col p-6 gap-6 overflow-y-auto">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider">
            Insights
          </span>
          <span className="badge-analyzing rounded-full px-2 py-0.5 text-xs font-medium">
            Analyzing…
          </span>
        </div>
        <Skeleton className="h-16 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-20 w-full rounded-xl" />
      </section>
    );
  }

  // ── Empty / no insight ──
  if (!insight) {
    return (
      <section className="flex flex-1 flex-col items-center justify-center p-6 text-center">
        <div className="text-5xl mb-4">📊</div>
        <p className="text-gray-400 text-sm">Analysis results will appear here</p>
        <p className="text-gray-300 text-xs mt-1">
          Upload a dataset and ask a question to get started
        </p>
      </section>
    );
  }

  // ── Not supported intent ──
  if (insight.not_supported) {
    return (
      <section className="flex flex-1 flex-col items-center justify-center p-6 text-center">
        <div className="text-5xl mb-4">💡</div>
        <p className="text-gray-500 text-sm mb-2">
          {insight.suggestion ?? "This type of question is not supported yet."}
        </p>
        <p className="text-gray-400 text-xs">
          Try asking: &quot;What affects retention?&quot;
        </p>
      </section>
    );
  }

  // ── Student Profile Analysis (6-section pipeline) ──
  if (insight.result_type === "student_profile_analysis") {
    return (
      <section className="flex flex-1 flex-col p-4 gap-4 overflow-y-auto">
        <StudentProfilePanel
          insight={insight as unknown as StudentProfileResult}
          fileId={undefined}
        />
      </section>
    );
  }

  // ── Scholarship prediction (EdTech Track) ──
  if (insight.result_type === "scholarship_prediction" && insight.school_matches) {
    return (
      <section className="flex flex-1 flex-col p-4 gap-4 overflow-y-auto">
        <ScholarshipResults insight={insight} />
        <SimulationPanel />
      </section>
    );
  }

  // ── Non-regression results: comparison, general, summary, descriptive, data_edit ──
  const rt = insight.result_type ?? "regression";
  if (rt === "comparison" || rt === "general" || rt === "descriptive" || rt === "not_supported" || rt === "data_edit") {
    const tableData = insight.table_data as any;
    // Build comparison chart data
    const comparisonChart = rt === "comparison" && tableData?.means
      ? Object.entries(tableData.means as Record<string, Record<string, number>>).map(
          ([group, vals]) => ({
            name: group.length > 18 ? group.slice(0, 16) + "…" : group,
            ...Object.fromEntries(
              (tableData.variables as string[] ?? []).map((v: string) => [
                v.replace(/ 2019/g, ""),
                vals[v] ?? 0,
              ])
            ),
          })
        )
      : null;

    // Build descriptive stats table data
    const descriptiveVars: any[] | null =
      rt === "descriptive" && tableData?.variables ? tableData.variables : null;

    // Web search citations
    const webCitations: Array<{ title: string; url: string }> | null =
      tableData?.web_search_result && tableData?.citations?.length
        ? tableData.citations
        : null;

    const chartColors = ["#6366F1", "#22C55E", "#F59E0B", "#EF4444", "#06B6D4", "#8B5CF6", "#EC4899", "#14B8A6"];

    return (
      <section className="flex flex-1 flex-col p-6 gap-5 overflow-y-auto min-h-0">
        <div className="flex items-center gap-2 mb-1 shrink-0">
          <span className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider">
            Insights
          </span>
          <span className="badge-ready rounded-full px-2 py-0.5 text-xs font-medium">
            Ready
          </span>
        </div>

        {/* ── (A) Summary ── */}
        <AnimatePresence>
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0 }}
            className="rounded-xl bg-[#F5F5F7] p-5 shrink-0"
          >
            {/* Render summary with preserved line breaks for web search answers */}
            {insight.summary.split("\n").map((line, i) => (
              <p key={i} className={`text-[#2D3561] leading-relaxed ${
                i === 0 ? "font-semibold text-base mb-1" : "text-sm mt-1"
              }`}>
                {line}
              </p>
            ))}
          </motion.div>
        </AnimatePresence>

        {/* ── (C1) Descriptive Statistics Table ── */}
        {descriptiveVars && descriptiveVars.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="rounded-xl border border-gray-100 p-4 overflow-x-auto shrink-0"
          >
            <h3 className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider mb-3">
              Descriptive Statistics
            </h3>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  {["Variable", "N", "Mean", "Std Dev", "Min", "Median", "Max", "Skew"].map((h) => (
                    <th key={h} className={`py-2 px-2 font-semibold text-[#2D3561] ${
                      h === "Variable" ? "text-left" : "text-right"
                    }`}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {descriptiveVars.map((v: any) => (
                  <tr key={v.name} className="border-b border-gray-50 hover:bg-[#F5F5F7]/60 transition-colors">
                    <td className="py-2 px-2 font-medium text-[#2D3561] max-w-[140px] truncate" title={v.name}>
                      {v.name}
                    </td>
                    <td className="py-2 px-2 text-right text-gray-500">{v.count}</td>
                    <td className="py-2 px-2 text-right text-[#2D3561] font-medium">{v.mean}</td>
                    <td className="py-2 px-2 text-right text-gray-500">{v.std}</td>
                    <td className="py-2 px-2 text-right text-gray-500">{v.min}</td>
                    <td className="py-2 px-2 text-right text-gray-500">{v.median}</td>
                    <td className="py-2 px-2 text-right text-gray-500">{v.max}</td>
                    <td className={`py-2 px-2 text-right ${
                      Math.abs(v.skewness ?? 0) > 1 ? "text-amber-500 font-medium" : "text-gray-400"
                    }`}>{(v.skewness ?? 0).toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-xs text-gray-400 mt-2">
              {descriptiveVars.length} variables · {tableData?.n_rows ?? "?"} observations
            </p>
          </motion.div>
        )}

        {/* ── (C2) Web Search Citations ── */}
        {webCitations && webCitations.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.25 }}
            className="rounded-xl border border-blue-100 bg-blue-50/40 p-4 shrink-0"
          >
            <h3 className="text-xs font-pixel text-blue-600 uppercase tracking-wider mb-2 flex items-center gap-1.5">
              <span>🌐</span> Nguồn / Sources
            </h3>
            <ul className="space-y-1">
              {webCitations.map((c, i) => (
                <li key={i} className="text-xs">
                  {c.url ? (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 hover:underline hover:text-blue-700 transition-colors"
                    >
                      {c.title || c.url}
                    </a>
                  ) : (
                    <span className="text-gray-500">{c.title}</span>
                  )}
                </li>
              ))}
            </ul>
          </motion.div>
        )}

        {/* ── (C3) Comparison Chart ── */}
        {comparisonChart && comparisonChart.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2 }}
            className="rounded-xl border border-gray-100 p-5 shrink-0"
          >
            <h3 className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider mb-4">
              Group Comparison
            </h3>
            <ResponsiveContainer width="100%" height={Math.max(comparisonChart.length * 52, 200)}>
              <BarChart data={comparisonChart} layout="vertical" margin={{ left: 10, right: 30, top: 5, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11, fill: "#6B7280" }}
                  axisLine={{ stroke: "#D1D5DB" }}
                  tickLine={{ stroke: "#D1D5DB" }}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={130}
                  tick={{ fontSize: 12, fill: "#2D3561", fontWeight: 500 }}
                  axisLine={{ stroke: "#D1D5DB" }}
                  tickLine={{ stroke: "#D1D5DB" }}
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (!active || !payload?.length) return null;
                    return (
                      <div className="rounded-lg bg-white shadow-lg border border-gray-100 px-3 py-2 text-xs">
                        <p className="font-semibold text-[#2D3561] mb-1">{label}</p>
                        {payload.map((p: any) => (
                          <p key={p.dataKey} style={{ color: p.color }}>
                            {p.dataKey}: {typeof p.value === "number" ? p.value.toFixed(3) : p.value}
                          </p>
                        ))}
                      </div>
                    );
                  }}
                />
                {(tableData?.variables as string[] ?? []).map((v: string, i: number) => (
                  <Bar
                    key={v}
                    dataKey={v.replace(/ 2019/g, "")}
                    fill={chartColors[i % chartColors.length]}
                    radius={[0, 4, 4, 0]}
                    barSize={16}
                    animationDuration={800}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </motion.div>
        )}

        {/* ── (B-alt) Comparison Table ── */}
        {tableData?.means && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.3 }}
            className="rounded-xl border border-gray-100 p-4 overflow-x-auto shrink-0"
          >
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 px-2 text-[#2D3561] font-semibold">
                    {tableData.group_column}
                  </th>
                  <th className="text-center py-2 px-1 text-gray-400 font-normal">N</th>
                  {(tableData.variables as string[]).map((v: string) => (
                    <th key={v} className="text-right py-2 px-2 text-[#2D3561] font-semibold">
                      {v.replace(/ 2019/g, "")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(tableData.groups as string[]).map((g: string) => {
                  const row = (tableData.means as any)[g] ?? {};
                  return (
                    <tr key={g} className="border-b border-gray-50 hover:bg-gray-50/50">
                      <td className="py-2 px-2 font-medium text-[#2D3561] whitespace-nowrap">{g}</td>
                      <td className="py-2 px-1 text-center text-gray-400">
                        {(tableData.group_sizes as any)?.[g] ?? "—"}
                      </td>
                      {(tableData.variables as string[]).map((v: string) => {
                        const val = row[v];
                        const allVals = (tableData.groups as string[]).map(
                          (gg: string) => (tableData.means as any)[gg]?.[v] ?? 0
                        );
                        const isMax = val === Math.max(...allVals);
                        const isMin = val === Math.min(...allVals);
                        return (
                          <td key={v} className={`py-2 px-2 text-right ${isMax ? "text-green-600 font-semibold" : isMin ? "text-red-500 font-semibold" : "text-gray-600"}`}>
                            {typeof val === "number" ? val.toFixed(3) : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </motion.div>
        )}

        {/* ── (C) Recommendation ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
          className="rounded-xl bg-[#FF6B4A]/8 border border-[#FF6B4A]/15 p-5 shrink-0"
        >
          <h3 className="text-xs font-pixel text-[#FF6B4A] uppercase tracking-wider mb-2">
            Recommendation
          </h3>
          <p className="text-[#2D3561] text-sm leading-relaxed font-medium">
            {insight.recommendation}
          </p>
        </motion.div>

        {/* ── (D) Analysis Details ── */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.3, delay: 0.6 }}
        >
          <Collapsible>
            <CollapsibleTrigger className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 transition-colors cursor-pointer">
              <span>▶</span>
              <span>Analysis Details</span>
            </CollapsibleTrigger>
            <CollapsibleContent className="mt-3 rounded-xl border border-gray-100 p-4 space-y-2 text-xs text-gray-500">
              <p>
                <span className="font-medium text-[#2D3561]">Type:</span>{" "}
                {rt === "comparison" ? "Group Comparison" : rt === "general" ? "General Q&A" : "Descriptive Statistics"}
              </p>
              <p>
                <span className="font-medium text-[#2D3561]">Method:</span>{" "}
                {rt === "comparison" ? "Group Mean Analysis" : rt === "general" ? "LLM Data Interpretation" : "Summary Statistics"}
              </p>
              {tableData?.n_groups && (
                <p>
                  <span className="font-medium text-[#2D3561]">Groups:</span>{" "}
                  {tableData.n_groups} ({tableData.group_column})
                </p>
              )}
              <p>
                <span className="font-medium text-[#2D3561]">Reasoning:</span>{" "}
                {insight.decision_trace.reason}
              </p>
            </CollapsibleContent>
          </Collapsible>
        </motion.div>
      </section>
    );
  }

  // ── Empty drivers (regression only) ──
  if (insight.drivers.length === 0) {
    return (
      <section className="flex flex-1 flex-col items-center justify-center p-6 text-center">
        <div className="text-5xl mb-4">🔍</div>
        <p className="text-gray-500 text-sm">
          We couldn&apos;t find strong drivers. Try a different question or check your
          dataset.
        </p>
      </section>
    );
  }

  // ── Chart data ──
  const chartData = insight.drivers.map((d) => ({
    name: d.name,
    value: Math.abs(d.coef),
    coef: d.coef,
    p_value: d.p_value,
    significant: d.significant,
    fill: d.coef >= 0 ? "#22C55E" : "#EF4444",
  }));

  return (
    <section className="flex flex-1 flex-col p-6 gap-5 overflow-y-auto">
      <div className="flex items-center gap-2 mb-1">
        <span className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider">
          Insights
        </span>
        <span className="badge-ready rounded-full px-2 py-0.5 text-xs font-medium">
          Ready
        </span>
      </div>

      {/* ── (A) Executive Summary ── */}
      <AnimatePresence>
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0 }}
          className="rounded-xl bg-[#F5F5F7] p-5"
        >
          <p className="font-semibold text-[#2D3561] text-lg leading-snug">
            {insight.summary}
          </p>
        </motion.div>
      </AnimatePresence>

      {/* ── (B) Driver Ranking ── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.2 }}
        className="rounded-xl border border-gray-100 p-5"
      >
        <h3 className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider mb-4">
          Driver Ranking
        </h3>
        <ResponsiveContainer width="100%" height={Math.max(insight.drivers.length * 56, 140)}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30, top: 5, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" horizontal={false} />
            <XAxis
              type="number"
              tick={{ fontSize: 11, fill: "#6B7280" }}
              axisLine={{ stroke: "#D1D5DB" }}
              tickLine={{ stroke: "#D1D5DB" }}
              label={{
                value: "Impact Strength",
                position: "insideBottom",
                offset: -10,
                style: { fontSize: 11, fill: "#9CA3AF" },
              }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={110}
              tick={{ fontSize: 13, fill: "#2D3561", fontWeight: 500 }}
              axisLine={{ stroke: "#D1D5DB" }}
              tickLine={{ stroke: "#D1D5DB" }}
            />
            <Tooltip
              content={({ active, payload }) => {
                if (!active || !payload?.[0]) return null;
                const d = payload[0].payload as (typeof chartData)[0];
                return (
                  <div className="rounded-lg bg-white shadow-lg border border-gray-100 px-3 py-2 text-xs">
                    <p className="font-semibold text-[#2D3561]">{d.name}</p>
                    <p className="text-gray-500">
                      Impact: {d.coef > 0 ? "+" : ""}
                      {d.coef.toFixed(3)}
                    </p>
                    <p className="text-gray-500">p-value: {d.p_value.toFixed(3)}</p>
                    <p className={d.significant ? "text-[#22C55E]" : "text-gray-400"}>
                      {d.significant ? "Significant" : "Not significant"}
                    </p>
                  </div>
                );
              }}
            />
            <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={24} animationDuration={800}>
              {chartData.map((entry, index) => (
                <Cell key={index} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </motion.div>

      {/* ── (C) Actionable Recommendation ── */}
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.4 }}
        className="rounded-xl bg-[#FF6B4A]/8 border border-[#FF6B4A]/15 p-5"
      >
        <h3 className="text-xs font-pixel text-[#FF6B4A] uppercase tracking-wider mb-2">
          Recommendation
        </h3>
        <p className="text-[#2D3561] text-sm leading-relaxed font-medium">
          {insight.recommendation}
        </p>
      </motion.div>

      {/* ── (D) Model Info (collapsed) ── */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 0.3, delay: 0.6 }}
      >
        <Collapsible>
          <CollapsibleTrigger className="flex items-center gap-2 text-xs text-gray-400 hover:text-gray-600 transition-colors cursor-pointer">
            <span>▶</span>
            <span>Model Details</span>
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-3 rounded-xl border border-gray-100 p-4 space-y-2 text-xs text-gray-500">
            <p>
              <span className="font-medium text-[#2D3561]">Model:</span>{" "}
              {insight.model_type === "regression" ? "OLS Regression" : "PLS-SEM"}
            </p>
            {insight.r2 !== null && (
              <p>
                <span className="font-medium text-[#2D3561]">R²:</span>{" "}
                {insight.r2.toFixed(3)}
              </p>
            )}
            <p>
              <span className="font-medium text-[#2D3561]">Confidence:</span>{" "}
              {insight.r2 !== null && insight.r2 > 0.5
                ? "High"
                : insight.r2 !== null && insight.r2 > 0.25
                  ? "Moderate"
                  : "Low"}
            </p>
            <p>
              <span className="font-medium text-[#2D3561]">Why this model:</span>{" "}
              {insight.decision_trace.reason}
            </p>
          </CollapsibleContent>
        </Collapsible>
      </motion.div>
    </section>
  );
}
