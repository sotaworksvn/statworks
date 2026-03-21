"use client";

import { useState, useCallback, useEffect } from "react";
import { useAppStore } from "@/lib/store";
import { useUser } from "@clerk/nextjs";
import { useRouter, useParams } from "next/navigation";
import type { InsightResult } from "@/lib/types";

/* ─── Ribbon Config ──────────────────────────────────────────────────────── */

interface RibbonAction {
  label: string;
  icon: string;
  description: string;
  queryTemplate: string;
  method?: string; // Direct dispatch — bypasses LLM intent parser
}

interface RibbonGroup {
  name: string;
  actions: RibbonAction[];
}

const SPSS_RIBBONS: RibbonGroup[] = [
  {
    name: "Analyze",
    actions: [
      { label: "Descriptive Statistics", icon: "📊", description: "Mean, median, std, min, max for all variables", queryTemplate: "Provide descriptive statistics for all variables", method: "descriptive" },
      { label: "Frequencies", icon: "📋", description: "Frequency distribution of variables", queryTemplate: "Show frequency analysis for the main variables", method: "frequencies" },
      { label: "Correlations", icon: "🔗", description: "Pearson correlation matrix", queryTemplate: "What are the correlations between all variables?", method: "correlations" },
      { label: "Regression (OLS)", icon: "📈", description: "Multiple linear regression", queryTemplate: "What drives the target variable? Use regression analysis" },
    ],
  },
  {
    name: "Graphs",
    actions: [
      { label: "Bar Chart", icon: "📊", description: "Driver coefficient chart", queryTemplate: "Show the driver coefficients as a bar chart analysis", method: "bar_chart" },
      { label: "Scatter Plot", icon: "🔘", description: "Variable relationship plot", queryTemplate: "Analyze the scatter relationship between key variables", method: "scatter" },
    ],
  },
];

const SMARTPLS_RIBBONS: RibbonGroup[] = [
  {
    name: "Model",
    actions: [
      { label: "PLS-SEM Path Model", icon: "🔀", description: "Structural equation modeling", queryTemplate: "Run a PLS-SEM path analysis on the data", method: "pls_sem" },
      { label: "Bootstrap Analysis", icon: "🔄", description: "Bootstrap significance testing", queryTemplate: "Perform bootstrap analysis for significance testing", method: "bootstrap" },
    ],
  },
  {
    name: "Assessment",
    actions: [
      { label: "Reliability", icon: "✅", description: "Internal consistency", queryTemplate: "Assess the reliability of the measurement model", method: "reliability" },
      { label: "Validity", icon: "🎯", description: "Convergent & discriminant validity", queryTemplate: "Check validity of the constructs", method: "validity" },
      { label: "Path Coefficients", icon: "➡️", description: "Structural path weights", queryTemplate: "Show the path coefficients between latent variables", method: "path_coefficients" },
    ],
  },
  {
    name: "Results",
    actions: [
      { label: "Effects Table", icon: "📋", description: "Direct, indirect, total effects", queryTemplate: "Show the effects table with direct and indirect effects", method: "effects_table" },
      { label: "Model Fit", icon: "📐", description: "SRMR, NFI, model quality", queryTemplate: "What is the overall model fit quality?", method: "model_fit" },
    ],
  },
];


/* ─── Result Renderers ───────────────────────────────────────────────────── */

function DescriptiveRenderer({ data }: { data: Record<string, any> }) {
  const vars = data?.variables ?? [];
  if (!vars.length) return <p className="text-gray-400">No numeric variables found.</p>;
  return (
    <div className="dashboard-table-scroll">
      <table className="dashboard-drivers-table">
        <thead>
          <tr>
            <th>Variable</th><th>N</th><th>Mean</th><th>Std</th><th>Min</th><th>Q25</th><th>Median</th><th>Q75</th><th>Max</th><th>Skew</th><th>Kurt</th>
          </tr>
        </thead>
        <tbody>
          {vars.map((v: any) => (
            <tr key={v.name}>
              <td className="font-medium">{v.name}</td>
              <td>{v.count}</td>
              <td>{v.mean}</td><td>{v.std}</td><td>{v.min}</td>
              <td>{v.q25}</td><td>{v.median}</td><td>{v.q75}</td>
              <td>{v.max}</td><td>{v.skewness}</td><td>{v.kurtosis}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FrequencyRenderer({ data }: { data: Record<string, any> }) {
  const vars = data?.variables ?? [];
  if (!vars.length) return <p className="text-gray-400">No variables to analyse.</p>;
  return (
    <div className="dashboard-freq-list">
      {vars.slice(0, 6).map((v: any) => (
        <details key={v.name} className="dashboard-freq-group">
          <summary className="dashboard-freq-summary">
            <strong>{v.name}</strong>
            <span className="text-xs text-gray-400 ml-2">
              ({v.n_unique} unique · {v.n_valid} valid · {v.n_missing} missing)
            </span>
          </summary>
          <table className="dashboard-drivers-table mt-2">
            <thead>
              <tr><th>Value</th><th>Count</th><th>%</th><th>Cum %</th></tr>
            </thead>
            <tbody>
              {(v.frequencies ?? []).slice(0, 15).map((f: any, i: number) => (
                <tr key={i}>
                  <td>{f.value}</td><td>{f.count}</td><td>{f.percent}%</td><td>{f.cumulative_percent}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ))}
    </div>
  );
}

function CorrelationRenderer({ data }: { data: Record<string, any> }) {
  const cols: string[] = data?.columns ?? [];
  const matrix: number[][] = data?.matrix ?? [];
  const sigPairs: any[] = data?.significant_pairs ?? [];
  if (!cols.length) return <p className="text-gray-400">No numeric variables for correlation.</p>;
  return (
    <div>
      <div className="dashboard-table-scroll">
        <table className="dashboard-drivers-table dashboard-corr-matrix">
          <thead>
            <tr><th></th>{cols.map((c) => <th key={c} className="text-xs">{c.length > 12 ? c.slice(0, 10) + "…" : c}</th>)}</tr>
          </thead>
          <tbody>
            {cols.map((row, i) => (
              <tr key={row}>
                <td className="font-medium text-xs">{row.length > 12 ? row.slice(0, 10) + "…" : row}</td>
                {matrix[i]?.map((val, j) => {
                  const abs = Math.abs(val);
                  const bg = i === j ? "var(--bg-muted)" : abs > 0.7 ? "rgba(34,197,94,0.15)" : abs > 0.4 ? "rgba(250,204,21,0.1)" : "transparent";
                  return <td key={j} style={{ background: bg, textAlign: "center" }}>{i === j ? "1" : val.toFixed(2)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {sigPairs.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-semibold text-gray-500 mb-1">Significant Pairs (p &lt; 0.05)</p>
          <div className="dashboard-sig-pairs">
            {sigPairs.slice(0, 10).map((p: any, i: number) => (
              <span key={i} className={`dashboard-sig-badge dashboard-sig-badge--${p.strength}`}>
                {p.var1} ↔ {p.var2}: r={p.r} ({p.strength})
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ScatterRenderer({ data }: { data: Record<string, any> }) {
  const points: { x: number; y: number }[] = data?.points ?? [];
  const xCol = data?.x_col ?? "X";
  const yCol = data?.y_col ?? "Y";
  const r = data?.r ?? 0;
  if (!points.length) return <p className="text-gray-400">No data points for scatter.</p>;

  // Simple SVG scatter
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;
  const w = 400, h = 250, pad = 30;

  return (
    <div>
      <svg viewBox={`0 0 ${w + pad * 2} ${h + pad * 2}`} className="dashboard-scatter-svg">
        {/* Axes */}
        <line x1={pad} y1={h + pad} x2={w + pad} y2={h + pad} stroke="#ddd" />
        <line x1={pad} y1={pad} x2={pad} y2={h + pad} stroke="#ddd" />
        <text x={w / 2 + pad} y={h + pad + 20} textAnchor="middle" className="dashboard-scatter-label">{xCol}</text>
        <text x={10} y={h / 2 + pad} textAnchor="middle" className="dashboard-scatter-label" transform={`rotate(-90, 10, ${h / 2 + pad})`}>{yCol}</text>
        {/* Points */}
        {points.map((p, i) => (
          <circle
            key={i}
            cx={pad + ((p.x - xMin) / xRange) * w}
            cy={pad + h - ((p.y - yMin) / yRange) * h}
            r={3} fill="#6366f1" opacity={0.6}
          />
        ))}
      </svg>
      <p className="text-xs text-gray-500 mt-1 text-center">
        r = {r} · n = {points.length} · {Math.abs(r) > 0.7 ? "Strong" : Math.abs(r) > 0.4 ? "Moderate" : "Weak"} correlation
      </p>
    </div>
  );
}

function ReliabilityRenderer({ data }: { data: Record<string, any> }) {
  const items: any[] = data?.items ?? [];
  const alpha = data?.cronbachs_alpha;
  const interp = data?.interpretation ?? "N/A";
  return (
    <div>
      <div className="dashboard-metric-cards">
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-value">{alpha?.toFixed(4) ?? "—"}</span>
          <span className="dashboard-metric-label">Cronbach&apos;s α</span>
        </div>
        <div className="dashboard-metric-card">
          <span className={`dashboard-metric-value ${alpha >= 0.7 ? "positive" : "negative"}`}>{interp}</span>
          <span className="dashboard-metric-label">Reliability</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-value">{data?.n_items ?? 0}</span>
          <span className="dashboard-metric-label">Items</span>
        </div>
      </div>
      {items.length > 0 && (
        <table className="dashboard-drivers-table mt-3">
          <thead>
            <tr><th>Item</th><th>Mean</th><th>Std</th><th>Item-Total r</th><th>α if Deleted</th></tr>
          </thead>
          <tbody>
            {items.map((it: any) => (
              <tr key={it.name}>
                <td className="font-medium">{it.name}</td>
                <td>{it.mean}</td><td>{it.std}</td>
                <td className={it.item_total_corr < 0.3 ? "negative" : ""}>{it.item_total_corr}</td>
                <td className={it.alpha_if_deleted > alpha ? "negative" : ""}>{it.alpha_if_deleted ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ValidityRenderer({ data }: { data: Record<string, any> }) {
  const loadings: any[] = data?.loadings ?? [];
  return (
    <div>
      <div className="dashboard-metric-cards">
        <div className="dashboard-metric-card">
          <span className={`dashboard-metric-value ${data?.convergent_valid ? "positive" : "negative"}`}>{data?.ave?.toFixed(4) ?? "—"}</span>
          <span className="dashboard-metric-label">AVE {data?.convergent_valid ? "✅" : "❌"}</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-value">{data?.composite_reliability?.toFixed(4) ?? "—"}</span>
          <span className="dashboard-metric-label">Composite Reliability</span>
        </div>
        <div className="dashboard-metric-card">
          <span className={`dashboard-metric-value ${data?.discriminant_valid ? "positive" : "negative"}`}>{data?.discriminant_valid ? "✅ Met" : "❌ Not met"}</span>
          <span className="dashboard-metric-label">Discriminant Validity</span>
        </div>
      </div>
      {loadings.length > 0 && (
        <table className="dashboard-drivers-table mt-3">
          <thead><tr><th>Indicator</th><th>Loading</th><th>Loading²</th><th>Communality</th></tr></thead>
          <tbody>
            {loadings.map((l: any) => (
              <tr key={l.name}>
                <td className="font-medium">{l.name}</td>
                <td className={l.loading < 0.5 ? "negative" : "positive"}>{l.loading}</td>
                <td>{l.loading_squared}</td><td>{l.communality}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ModelFitRenderer({ data }: { data: Record<string, any> }) {
  const indicators: any[] = data?.indicators ?? [];
  return (
    <div>
      <div className="dashboard-metric-cards">
        <div className="dashboard-metric-card">
          <span className={`dashboard-metric-value ${data?.quality === "Good" ? "positive" : data?.quality === "Moderate" ? "" : "negative"}`}>{data?.quality ?? "—"}</span>
          <span className="dashboard-metric-label">Overall Quality</span>
        </div>
      </div>
      {indicators.length > 0 && (
        <table className="dashboard-drivers-table mt-3">
          <thead><tr><th>Metric</th><th>Value</th><th>Threshold</th><th>Acceptable</th></tr></thead>
          <tbody>
            {indicators.map((ind: any) => (
              <tr key={ind.metric}>
                <td className="font-medium">{ind.metric}</td>
                <td>{typeof ind.value === "number" ? ind.value.toFixed(4) : ind.value}</td>
                <td className="text-gray-400">{ind.threshold}</td>
                <td>{ind.acceptable ? "✅" : "❌"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

/* ─── Bar Chart Renderer ──────────────────────────────────────────────── */

function BarChartRenderer({ data }: { data: Record<string, any> }) {
  const rawBars: any[] = data?.bars ?? [];
  if (!rawBars.length) return <p className="text-gray-400">No data for bar chart.</p>;

  // Sort by absolute coefficient descending
  const bars = [...rawBars].sort((a, b) => Math.abs(b.coefficient) - Math.abs(a.coefficient));
  const maxAbs = Math.max(...bars.map((b) => Math.abs(b.coefficient)), 0.001);

  const labelW = 140;     // left label column
  const halfBarW = 140;   // max bar extent on each side of center
  const valueW = 70;      // value label space on each side
  const pW = 60;          // p-value column
  const centerX = labelW + valueW + halfBarW;  // zero axis position
  const totalW = labelW + valueW + halfBarW * 2 + valueW + pW;
  const barH = 26;
  const gap = 12;
  const padTop = 10;
  const svgH = padTop + bars.length * (barH + gap) + 4;

  return (
    <div>
      <svg viewBox={`0 0 ${totalW} ${svgH}`} className="dashboard-barchart-svg">
        {/* Zero axis */}
        <line x1={centerX} y1={2} x2={centerX} y2={svgH - 2}
          stroke="#d1d5db" strokeWidth={1.5} />
        <text x={centerX} y={padTop - 2} textAnchor="middle" fontSize="8" fill="#b0b0b0">0</text>

        {bars.map((b: any, i: number) => {
          const y = padTop + i * (barH + gap);
          const barW = (Math.abs(b.coefficient) / maxAbs) * halfBarW;
          const isPositive = b.coefficient >= 0;
          const color = b.significant
            ? (isPositive ? "#22c55e" : "#ef4444")
            : "#d1d5db";
          const textColor = b.significant
            ? (isPositive ? "#16a34a" : "#dc2626")
            : "#9ca3af";

          // Bar position: positive grows right from center, negative grows left
          const barX = isPositive ? centerX : centerX - barW;

          // Value label position: just outside the bar end
          const valX = isPositive ? centerX + barW + 6 : centerX - barW - 6;
          const valAnchor = isPositive ? "start" : "end";

          return (
            <g key={b.name}>
              {/* Variable name — left column */}
              <text x={labelW - 8} y={y + barH / 2 + 4} textAnchor="end"
                fontSize="11" fill="#374151" fontWeight="500">
                {b.name}
              </text>

              {/* Bar (diverging from center) */}
              <rect x={barX} y={y + 2} width={Math.max(barW, 2)} height={barH - 4}
                rx={3} fill={color} opacity={0.85} />

              {/* Coefficient value — outside bar end */}
              <text x={valX} y={y + barH / 2 + 4} textAnchor={valAnchor}
                fontSize="10" fill={textColor} fontWeight="700" fontFamily="var(--font-mono, monospace)">
                {b.coefficient >= 0 ? "+" : ""}{b.coefficient.toFixed(4)}
              </text>

              {/* p-value — far right */}
              <text x={totalW - 4} y={y + barH / 2 + 4} textAnchor="end"
                fontSize="9" fill="#b0b0b0">
                p={b.p_value.toFixed(3)}
              </text>

              {/* Horizontal grid line */}
              <line x1={labelW} y1={y + barH + gap / 2} x2={totalW - pW} y2={y + barH + gap / 2}
                stroke="#f3f4f6" strokeWidth={0.5} />
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="dashboard-bar-legend">
        <span className="dashboard-bar-legend-item"><span style={{ background: "#22c55e" }} className="dashboard-legend-dot" /> Significant (+)</span>
        <span className="dashboard-bar-legend-item"><span style={{ background: "#ef4444" }} className="dashboard-legend-dot" /> Significant (−)</span>
        <span className="dashboard-bar-legend-item"><span style={{ background: "#d1d5db" }} className="dashboard-legend-dot" /> Not significant</span>
      </div>
    </div>
  );
}

/* ─── Bootstrap Renderer ─────────────────────────────────────────────── */

function BootstrapRenderer({ data }: { data: Record<string, any> }) {
  const results: any[] = data?.results ?? [];
  if (!results.length) return <p className="text-gray-400">No bootstrap results.</p>;
  return (
    <div>
      <div className="dashboard-metric-cards">
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-value">{data?.n_bootstrap ?? 0}</span>
          <span className="dashboard-metric-label">Subsamples</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-value">{data?.n_observations ?? 0}</span>
          <span className="dashboard-metric-label">Observations</span>
        </div>
        <div className="dashboard-metric-card">
          <span className="dashboard-metric-value">{results.filter((r) => r.significant).length}/{results.length}</span>
          <span className="dashboard-metric-label">Significant</span>
        </div>
      </div>
      <div className="dashboard-table-scroll">
        <table className="dashboard-drivers-table">
          <thead>
            <tr>
              <th>Path</th><th>Original (O)</th><th>Mean (M)</th><th>STDEV</th>
              <th>T Statistics</th><th>P Values</th><th>2.5%</th><th>97.5%</th><th>Sig</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r: any) => (
              <tr key={r.name}>
                <td className="font-medium">{r.name} → {data.target}</td>
                <td>{r.original_sample}</td>
                <td>{r.sample_mean}</td>
                <td>{r.std_dev}</td>
                <td className={r.t_statistic > 1.96 ? "positive" : ""}>{r.t_statistic}</td>
                <td className={r.p_value < 0.05 ? "positive" : "negative"}>{r.p_value}</td>
                <td>{r.ci_lower}</td>
                <td>{r.ci_upper}</td>
                <td>{r.significant ? "✅" : "❌"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── Path Model Renderer ────────────────────────────────────────────── */

function PathModelRenderer({ data }: { data: Record<string, any> }) {
  const paths: any[] = data?.paths ?? [];
  const target = data?.target ?? "Target";
  if (!paths.length) return <p className="text-gray-400">No path data.</p>;

  const svgW = 500, svgH = Math.max(200, paths.length * 50 + 60);
  const targetX = svgW - 80, targetY = svgH / 2;

  return (
    <div>
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="dashboard-pathmodel-svg">
        {/* Target node */}
        <rect x={targetX - 50} y={targetY - 18} width={100} height={36} rx={6} fill="#6366f1" opacity={0.9} />
        <text x={targetX} y={targetY + 5} textAnchor="middle" fill="white" fontSize="11" fontWeight="bold">
          {target.length > 12 ? target.slice(0, 10) + "…" : target}
        </text>
        {data?.r_squared != null && (
          <text x={targetX} y={targetY + 30} textAnchor="middle" fontSize="10" fill="#6366f1">
            R² = {data.r_squared.toFixed(4)}
          </text>
        )}

        {/* Predictor nodes + arrows */}
        {paths.map((p: any, i: number) => {
          const fromX = 50, fromY = 30 + i * 45;
          const color = p.significant ? "#22c55e" : "#9ca3af";
          return (
            <g key={p.from}>
              {/* From node */}
              <rect x={fromX - 45} y={fromY - 14} width={90} height={28} rx={4}
                fill={p.significant ? "rgba(34,197,94,0.1)" : "#f3f4f6"} stroke={color} strokeWidth={1.5} />
              <text x={fromX} y={fromY + 4} textAnchor="middle" fontSize="9" fill="#374151">
                {p.from.length > 12 ? p.from.slice(0, 10) + "…" : p.from}
              </text>
              {/* Arrow */}
              <line x1={fromX + 45} y1={fromY} x2={targetX - 55} y2={targetY} stroke={color} strokeWidth={p.significant ? 2 : 1} markerEnd="url(#arrow)" />
              {/* Coefficient label */}
              <text x={(fromX + 50 + targetX - 55) / 2} y={(fromY + targetY) / 2 - 5}
                textAnchor="middle" fontSize="9" fill={color} fontWeight="600">
                {p.coefficient} {p.t_statistic ? `(t=${p.t_statistic.toFixed(1)})` : ""}
              </text>
            </g>
          );
        })}
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
          </marker>
        </defs>
      </svg>
    </div>
  );
}

/* ─── Effects Table Renderer ─────────────────────────────────────────── */

function EffectsRenderer({ data }: { data: Record<string, any> }) {
  const direct: any[] = data?.direct_effects ?? [];
  const indirect: any[] = data?.indirect_effects ?? [];
  const total: any[] = data?.total_effects ?? [];

  return (
    <div className="dashboard-effects-sections">
      {/* Direct Effects */}
      <div className="dashboard-effects-section">
        <h5 className="dashboard-effects-title">Direct Effects</h5>
        <table className="dashboard-drivers-table">
          <thead><tr><th>Variable</th><th>Effect</th><th>p-value</th><th>Sig</th></tr></thead>
          <tbody>
            {direct.map((d: any) => (
              <tr key={d.name}>
                <td className="font-medium">{d.name}</td>
                <td className={d.effect > 0 ? "positive" : "negative"}>{d.effect}</td>
                <td>{d.p_value}</td>
                <td>{d.significant ? "✅" : "❌"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Indirect Effects */}
      {indirect.length > 0 && (
        <div className="dashboard-effects-section">
          <h5 className="dashboard-effects-title">Indirect Effects</h5>
          <table className="dashboard-drivers-table">
            <thead><tr><th>From</th><th>Via</th><th>To</th><th>Effect</th></tr></thead>
            <tbody>
              {indirect.map((ie: any, i: number) => (
                <tr key={i}>
                  <td>{ie.from}</td>
                  <td className="font-medium">{ie.via}</td>
                  <td>{ie.to}</td>
                  <td className={ie.effect > 0 ? "positive" : "negative"}>{ie.effect}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Total Effects */}
      <div className="dashboard-effects-section">
        <h5 className="dashboard-effects-title">Total Effects</h5>
        <table className="dashboard-drivers-table">
          <thead><tr><th>Variable</th><th>Direct</th><th>Indirect</th><th>Total</th></tr></thead>
          <tbody>
            {total.map((t: any) => (
              <tr key={t.name}>
                <td className="font-medium">{t.name}</td>
                <td>{t.direct}</td>
                <td>{t.indirect}</td>
                <td className={t.total > 0 ? "positive" : "negative"} style={{ fontWeight: 600 }}>{t.total}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── Path Coefficients Renderer ─────────────────────────────────────── */

function PathCoefficientsRenderer({ data }: { data: Record<string, any> }) {
  const paths: any[] = data?.paths ?? [];
  const target = data?.target ?? "Target";
  if (!paths.length) return <p className="text-gray-400">No path coefficient data.</p>;

  // --- SVG Path Diagram (SmartPLS-style) ---
  const nodeW = 110, nodeH = 32, circleR = 38;
  const svgW = 560;
  const rowGap = 52;
  const svgH = Math.max(250, paths.length * rowGap + 80);
  const targetCX = svgW - 70, targetCY = svgH / 2;

  return (
    <div>
      {/* Visual Path Diagram */}
      <svg viewBox={`0 0 ${svgW} ${svgH}`} className="dashboard-pathmodel-svg">
        <defs>
          <marker id="pcarrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#6366f1" />
          </marker>
          <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" floodOpacity="0.08" />
          </filter>
        </defs>

        {/* Target construct (blue circle) */}
        <circle cx={targetCX} cy={targetCY} r={circleR} fill="#6366f1" filter="url(#shadow)" />
        <text x={targetCX} y={targetCY - 4} textAnchor="middle" fill="white" fontSize="10" fontWeight="bold">
          {target.length > 14 ? target.slice(0, 12) + "…" : target}
        </text>
        {data?.r_squared != null && (
          <text x={targetCX} y={targetCY + 12} textAnchor="middle" fill="rgba(255,255,255,0.85)" fontSize="9">
            R² = {data.r_squared.toFixed(3)}
          </text>
        )}

        {/* Predictor nodes + paths */}
        {paths.map((p: any, i: number) => {
          const fromX = 65;
          const fromY = 25 + i * rowGap;
          const isSignificant = p.significant;
          const pathColor = isSignificant ? "#22c55e" : "#b0b0b0";
          const lineWidth = isSignificant ? 2.5 : 1;
          const nodeStroke = isSignificant ? "#22c55e" : "#d1d5db";
          const nodeFill = isSignificant ? "rgba(34,197,94,0.06)" : "#fafafa";
          const arrowEndX = targetCX - circleR - 2;
          const arrowEndY = targetCY;

          // Midpoint for label
          const midX = (fromX + nodeW / 2 + arrowEndX) / 2;
          const midY = (fromY + arrowEndY) / 2;

          return (
            <g key={p.name}>
              {/* Predictor node (rounded rect) */}
              <rect x={fromX - nodeW / 2} y={fromY - nodeH / 2} width={nodeW} height={nodeH}
                rx={5} fill={nodeFill} stroke={nodeStroke} strokeWidth={1.5} filter="url(#shadow)" />
              <text x={fromX} y={fromY + 4} textAnchor="middle" fontSize="9" fill="#374151" fontWeight="500">
                {p.name.length > 15 ? p.name.slice(0, 13) + "…" : p.name}
              </text>

              {/* Arrow to target */}
              <line x1={fromX + nodeW / 2} y1={fromY} x2={arrowEndX} y2={arrowEndY}
                stroke={pathColor} strokeWidth={lineWidth} markerEnd="url(#pcarrow)" />

              {/* Coefficient + t-stat on the arrow */}
              <rect x={midX - 42} y={midY - 18} width={84} height={22} rx={4}
                fill="white" stroke={pathColor} strokeWidth={0.8} opacity={0.95} />
              <text x={midX} y={midY - 4} textAnchor="middle" fontSize="9" fill={pathColor} fontWeight="700">
                β = {p.coefficient}
              </text>
              {p.t_statistic != null && (
                <text x={midX} y={midY + 8} textAnchor="middle" fontSize="7.5" fill="#9ca3af">
                  t = {p.t_statistic.toFixed(2)} | p = {p.p_value}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Compact summary table */}
      <div className="dashboard-table-scroll" style={{ marginTop: "0.75rem" }}>
        <table className="dashboard-drivers-table">
          <thead>
            <tr><th>Path</th><th>β</th><th>T</th><th>P</th><th>95% CI</th><th>Sig</th></tr>
          </thead>
          <tbody>
            {paths.map((p: any) => (
              <tr key={p.name}>
                <td className="font-medium">{p.name} → {target}</td>
                <td className={p.coefficient > 0 ? "positive" : "negative"}>{p.coefficient}</td>
                <td className={p.t_statistic > 1.96 ? "positive" : ""}>{p.t_statistic?.toFixed(3)}</td>
                <td>{p.p_value}</td>
                <td style={{ fontSize: "0.7rem" }}>[{p.ci_lower ?? "—"}, {p.ci_upper ?? "—"}]</td>
                <td>{p.significant ? "✅" : "❌"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── Comparison Renderer ─────────────────────────────────────────── */
function ComparisonRenderer({ data }: { data: any }) {
  const groups = data?.groups ?? [];
  const variables = data?.variables ?? [];
  const means = data?.means ?? {};
  const groupCol = data?.group_column ?? "Group";
  const groupSizes = data?.group_sizes ?? {};

  if (groups.length === 0) return <p>No comparison data available.</p>;

  return (
    <div className="dashboard-table-scroll">
      <table className="dashboard-drivers-table" style={{ fontSize: "0.75rem" }}>
        <thead>
          <tr>
            <th>{groupCol}</th>
            <th style={{ fontSize: "0.65rem", color: "#9ca3af" }}>N</th>
            {variables.map((v: string) => (
              <th key={v}>{v.replace(/ 2019/g, "")}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((g: string) => {
            const row = means[g] ?? {};
            return (
              <tr key={g}>
                <td style={{ fontWeight: 500, whiteSpace: "nowrap" }}>{g}</td>
                <td style={{ color: "#9ca3af" }}>{groupSizes[g] ?? "—"}</td>
                {variables.map((v: string) => {
                  const val = row[v];
                  // Find min/max across groups for this variable
                  const allVals = groups.map((gg: string) => means[gg]?.[v] ?? 0);
                  const maxVal = Math.max(...allVals);
                  const minVal = Math.min(...allVals);
                  const isMax = val === maxVal;
                  const isMin = val === minVal;
                  return (
                    <td key={v}
                      className={isMax ? "positive" : isMin ? "negative" : ""}
                      style={{ fontWeight: isMax || isMin ? 600 : 400 }}
                    >
                      {typeof val === "number" ? val.toFixed(3) : "—"}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ─── General / Text Answer Renderer ─────────────────────────────── */
function GeneralRenderer({ result }: { result: any }) {
  return (
    <div style={{ padding: "1.2rem", lineHeight: 1.7 }}>
      <div style={{
        background: "rgba(99,102,241,0.06)", borderRadius: "0.75rem",
        padding: "1rem 1.2rem", border: "1px solid rgba(99,102,241,0.15)",
        marginBottom: "0.8rem", fontSize: "0.95rem", color: "#1e1b4b"
      }}>
        {result.summary}
      </div>
      {result.recommendation && (
        <div style={{
          background: "rgba(234,88,12,0.04)", borderRadius: "0.75rem",
          padding: "0.8rem 1rem", border: "1px solid rgba(234,88,12,0.12)",
          fontSize: "0.85rem", color: "#9a3412"
        }}>
          <strong style={{ color: "#ea580c" }}>💡 Suggestion: </strong>{result.recommendation}
        </div>
      )}
    </div>
  );
}

/* ─── Not Supported Renderer ─────────────────────────────────────── */
function NotSupportedRenderer({ result }: { result: any }) {
  return (
    <div style={{ padding: "1.5rem", textAlign: "center" }}>
      <div style={{
        background: "rgba(245,158,11,0.08)", borderRadius: "1rem",
        padding: "1.5rem", border: "1px solid rgba(245,158,11,0.2)",
        maxWidth: "400px", margin: "0 auto"
      }}>
        <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>⚠️</div>
        <p style={{ fontSize: "0.95rem", color: "#92400e", marginBottom: "0.75rem", lineHeight: 1.6 }}>
          {result.summary}
        </p>
        {result.suggestion && (
          <p style={{ fontSize: "0.8rem", color: "#b45309", fontStyle: "italic" }}>
            {result.suggestion}
          </p>
        )}
        {result.recommendation && (
          <p style={{ fontSize: "0.8rem", color: "#78716c", marginTop: "0.5rem" }}>
            {result.recommendation}
          </p>
        )}
      </div>
    </div>
  );
}

/* ─── Master Result Renderer ─────────────────────────────────────────────── */

function ResultBody({ result }: { result: InsightResult }) {
  const rt = result.result_type ?? "regression";
  const td = result.table_data;

  // Render type-specific component
  if (rt === "descriptive" && td) return <DescriptiveRenderer data={td} />;
  if (rt === "frequency" && td) return <FrequencyRenderer data={td} />;
  if (rt === "correlation" && td) return <CorrelationRenderer data={td} />;
  if (rt === "scatter" && td) return <ScatterRenderer data={td} />;
  if (rt === "reliability" && td) return <ReliabilityRenderer data={td} />;
  if (rt === "validity" && td) return <ValidityRenderer data={td} />;
  if (rt === "model_fit" && td) return <ModelFitRenderer data={td} />;
  if (rt === "bar_chart" && td) return <BarChartRenderer data={td} />;
  if (rt === "bootstrap" && td) return <BootstrapRenderer data={td} />;
  if (rt === "path_model" && td) return <PathModelRenderer data={td} />;
  if (rt === "effects" && td) return <EffectsRenderer data={td} />;
  if (rt === "path_coefficients" && td) return <PathCoefficientsRenderer data={td} />;
  if (rt === "comparison" && td) return <ComparisonRenderer data={td} />;
  if (rt === "general") return <GeneralRenderer result={result} />;
  if (rt === "not_supported") return <NotSupportedRenderer result={result} />;

  // Default: regression (existing driver table)
  return (
    <>
      {result.drivers.length > 0 && (
        <div className="dashboard-result-drivers">
          <table className="dashboard-drivers-table">
            <thead>
              <tr><th>Variable</th><th>Coefficient</th><th>p-value</th><th>Significant</th></tr>
            </thead>
            <tbody>
              {result.drivers.map((d) => (
                <tr key={d.name}>
                  <td>{d.name}</td>
                  <td className={d.coef > 0 ? "positive" : "negative"}>{d.coef.toFixed(4)}</td>
                  <td>{d.p_value.toFixed(4)}</td>
                  <td>{d.significant ? "✅" : "❌"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {result.r2 != null && (
        <div className="dashboard-result-r2">R² = {result.r2.toFixed(4)}</div>
      )}
    </>
  );
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export function Dashboard() {
  const { fileId } = useAppStore();
  const { user } = useUser();
  const router = useRouter();
  const params = useParams();
  const slug = params.slug as string[] | undefined;

  // Read initial tab from URL slug
  const initialTab = slug?.[1] === "impact-analysis" ? "smartpls" : "spss";
  const [activeTab, setActiveTab] = useState<"spss" | "smartpls">(initialTab);
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<{ label: string; data: InsightResult }[]>([]);

  const handleTabSwitch = (tab: "spss" | "smartpls") => {
    setActiveTab(tab);
    router.push(tab === "smartpls" ? "/app/monitor/impact-analysis" : "/app/monitor/data-analysis");
  };

  const ribbons = activeTab === "spss" ? SPSS_RIBBONS : SMARTPLS_RIBBONS;

  const handleAction = useCallback(async (action: RibbonAction) => {
    if (!fileId || isRunning) return;

    setIsRunning(true);
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const res = await fetch(`${backendUrl}/api/chat/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_id: fileId, query: action.queryTemplate, method: action.method ?? null }),
      });

      if (res.ok) {
        const data = await res.json();
        setResults((prev) => [{ label: action.label, data }, ...prev]);

        // Autosave to history (fire-and-forget)
        fetch(`${backendUrl}/api/history`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(user?.id ? { "x-clerk-user-id": user.id } : {}),
          },
          body: JSON.stringify({
            category: "dashboard",
            title: `${action.label}: ${data.summary?.slice(0, 50) || "Analysis complete"}`,
            snapshot: {
              query: action.queryTemplate,
              result_type: data.result_type,
              summary: data.summary,
              r2: data.r2,
            },
          }),
        }).catch((err) => console.warn("[history autosave] dashboard:", err));
      }
    } catch {
      // Silently fail
    } finally {
      setIsRunning(false);
    }
  }, [fileId, isRunning, user?.id]);

  if (!fileId) {
    return (
      <div className="dashboard-empty">
        <div className="dashboard-empty-icon">📈</div>
        <h3>No Dataset Loaded</h3>
        <p>Upload a dataset to access the professional analysis dashboard.</p>
      </div>
    );
  }

  return (
    <div className="dashboard">
      {/* ── Tab Switcher ───────────────────────────────────── */}
      <div className="dashboard-tabs">
        <button
          className={`dashboard-tab ${activeTab === "spss" ? "dashboard-tab--active" : ""}`}
          onClick={() => handleTabSwitch("spss")}
        >
          <span className="dashboard-tab-icon">📊</span>
          Data Analysis
        </button>
        <button
          className={`dashboard-tab ${activeTab === "smartpls" ? "dashboard-tab--active" : ""}`}
          onClick={() => handleTabSwitch("smartpls")}
        >
          <span className="dashboard-tab-icon">🔀</span>
          Impact Analysis
        </button>
      </div>

      {/* ── Ribbon Menu ────────────────────────────────────── */}
      <div className="dashboard-ribbon">
        {ribbons.map((group) => (
          <div key={group.name} className="dashboard-ribbon-group">
            <div className="dashboard-ribbon-group-label">{group.name}</div>
            <div className="dashboard-ribbon-actions">
              {group.actions.map((action) => (
                <button
                  key={action.label}
                  className="dashboard-ribbon-btn"
                  onClick={() => handleAction(action)}
                  disabled={isRunning}
                  title={action.description}
                >
                  <span className="dashboard-ribbon-btn-icon">{action.icon}</span>
                  <span className="dashboard-ribbon-btn-label">{action.label}</span>
                </button>
              ))}
            </div>
          </div>
        ))}

        {isRunning && (
          <div className="dashboard-ribbon-spinner">
            <div className="dashboard-spinner" />
            Running analysis...
          </div>
        )}
      </div>

      {/* ── Results Area ───────────────────────────────────── */}
      <div className="dashboard-results">
        {results.length === 0 ? (
          <div className="dashboard-results-empty">
            <p>Click a ribbon action above to run an analysis.</p>
            <p className="dashboard-results-hint">
              Results will appear here as stackable panels.
            </p>
          </div>
        ) : (
          results.map((result, i) => (
            <div key={i} className="dashboard-result-panel">
              <div className="dashboard-result-header">
                <h4>{result.label}</h4>
                <div className="dashboard-result-badges">
                  {result.data.result_type && (
                    <span className="dashboard-result-type">{result.data.result_type.toUpperCase()}</span>
                  )}
                  {result.data.model_type && (
                    <span className="dashboard-result-model">{result.data.model_type.toUpperCase()}</span>
                  )}
                </div>
              </div>
              <div className="dashboard-result-body">
                <div className="dashboard-result-summary">{result.data.summary}</div>
                <ResultBody result={result.data} />
                <div className="dashboard-result-recommendation">
                  💡 {result.data.recommendation}
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
