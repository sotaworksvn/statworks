"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { SimulationResult } from "@/lib/types";

interface Factor {
  key: string;
  label: string;
  min: number;
  max: number;
  step: number;
  default: number;
}

const FACTORS: Factor[] = [
  { key: "gpa", label: "GPA", min: 2.0, max: 4.0, step: 0.1, default: 3.5 },
  { key: "sat_score", label: "SAT", min: 800, max: 1600, step: 10, default: 1400 },
  { key: "ielts_score", label: "IELTS", min: 5.0, max: 9.0, step: 0.5, default: 7.0 },
];

export function SimulationPanel() {
  const { insight, fileId } = useAppStore();
  const [selectedSchool, setSelectedSchool] = useState("");
  const [selectedFactor, setSelectedFactor] = useState("sat_score");
  const [factorValue, setFactorValue] = useState(1400);
  const [simulation, setSimulation] = useState<SimulationResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const matches = insight?.school_matches ?? [];
  const currentFactor = FACTORS.find((f) => f.key === selectedFactor) ?? FACTORS[1];

  const runSimulation = async () => {
    if (!fileId || !selectedSchool) return;

    setIsLoading(true);
    try {
      const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
      const res = await fetch(`${backendUrl}/api/scholarship/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          file_id: fileId,
          school_name: selectedSchool,
          improvements: { [selectedFactor]: factorValue },
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setSimulation(data as SimulationResult);
      }
    } catch (err) {
      console.error("Simulation failed:", err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 space-y-4">
      <h3 className="font-semibold text-[#2D3561] text-base">🎮 Mô Phỏng Cải Thiện</h3>

      {/* School selector */}
      <div>
        <label className="text-xs font-medium text-gray-500 mb-1 block">Chọn trường</label>
        <select
          className="w-full rounded-lg border border-gray-200 bg-white p-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#2D3561]/30"
          value={selectedSchool}
          onChange={(e) => {
            setSelectedSchool(e.target.value);
            setSimulation(null);
          }}
        >
          <option value="">-- Chọn trường để mô phỏng --</option>
          {matches.slice(0, 15).map((m) => (
            <option key={m.school_name} value={m.school_name}>
              {m.school_name} ({m.match_score}% — {m.match_level === "dream" ? "Mơ ước" : m.match_level === "target" ? "Phù hợp" : "An toàn"})
            </option>
          ))}
        </select>
      </div>

      {/* Factor selector */}
      <div>
        <label className="text-xs font-medium text-gray-500 mb-1 block">Yếu tố cần cải thiện</label>
        <div className="flex gap-2">
          {FACTORS.map((factor) => (
            <button
              key={factor.key}
              className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedFactor === factor.key
                  ? "bg-[#FF6B4A] text-white"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200"
              }`}
              onClick={() => {
                setSelectedFactor(factor.key);
                setFactorValue(factor.default);
                setSimulation(null);
              }}
            >
              {factor.label}
            </button>
          ))}
        </div>
      </div>

      {/* Value slider */}
      <div>
        <label className="text-xs font-medium text-gray-500 mb-1 block">
          Giá trị mục tiêu:{" "}
          <span className="font-bold text-[#FF6B4A]">{factorValue}</span>
        </label>
        <input
          type="range"
          className="w-full accent-[#FF6B4A]"
          min={currentFactor.min}
          max={currentFactor.max}
          step={currentFactor.step}
          value={factorValue}
          onChange={(e) => {
            setFactorValue(parseFloat(e.target.value));
            setSimulation(null);
          }}
        />
        <div className="flex justify-between text-xs text-gray-400 mt-0.5">
          <span>{currentFactor.min}</span>
          <span>{currentFactor.max}</span>
        </div>
      </div>

      {/* Run button */}
      <button
        className="w-full rounded-lg bg-[#2D3561] py-2.5 text-white text-sm font-semibold hover:bg-[#3a4578] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        onClick={runSimulation}
        disabled={!selectedSchool || isLoading}
      >
        {isLoading ? "Đang tính toán..." : "Xem kết quả mô phỏng"}
      </button>

      {/* Result */}
      {simulation && (
        <div className="rounded-xl bg-[#FF6B4A]/10 border border-[#FF6B4A]/20 p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Khả năng đỗ hiện tại</span>
            <span className="font-bold text-gray-700">{simulation.current_score}%</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Sau khi cải thiện</span>
            <span className="text-2xl font-bold text-[#FF6B4A]">{simulation.new_score}%</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">Thay đổi</span>
            <span className={`font-bold text-base ${simulation.delta >= 0 ? "text-green-600" : "text-red-500"}`}>
              {simulation.delta >= 0 ? "+" : ""}{simulation.delta}%
            </span>
          </div>
          {simulation.level_change && (
            <div className="mt-2 rounded-lg bg-white/70 px-3 py-2 text-sm text-[#2D3561] font-medium">
              📈 {simulation.level_change}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
