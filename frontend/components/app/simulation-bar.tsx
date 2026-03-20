"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/store";
import { simulateScenario } from "@/lib/api";
import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { ResultBadge } from "./result-badge";
import { motion, AnimatePresence } from "framer-motion";

export function SimulationBar() {
  const {
    fileId,
    user,
    insight,
    simulation,
    setSimulation,
    setIsSimulating,
    setSimulateError,
    isSimulating,
    simulateError,
  } = useAppStore();

  const [selectedVar, setSelectedVar] = useState("");
  const [delta, setDelta] = useState(20);

  // Derive driver names (safe even when insight is null)
  const driverNames = insight?.drivers.map((d) => d.name) ?? [];
  const activeVar = selectedVar || driverNames[0] || "";

  // All hooks MUST be called before any early return
  const simulateMutation = useMutation({
    mutationFn: async () => {
      if (!fileId) throw new Error("No dataset loaded");
      return simulateScenario(fileId, activeVar, delta / 100, user?.id);
    },
    onMutate: () => {
      setIsSimulating(true);
      setSimulateError(null);
    },
    onSuccess: (data) => {
      setSimulation(data);
      setIsSimulating(false);
    },
    onError: (err) => {
      const raw = err instanceof Error ? err.message : "Simulation failed";
      // Detect stale file_id (backend was restarted)
      const message = raw.includes("not found")
        ? "Session expired — please re-upload your dataset"
        : raw;
      setSimulateError(message);
      setIsSimulating(false);
      toast.error(message, { duration: 5000 });
    },
  });

  // Only visible after a successful /analyze with drivers
  if (!insight || insight.not_supported || insight.drivers.length === 0) {
    return null;
  }

  return (
    <motion.footer
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.5 }}
      className="shrink-0 border-t border-gray-100 bg-white px-6 py-3"
    >
      <div className="flex items-center gap-4">
        <span className="text-xs font-pixel text-[#2D3561] uppercase tracking-wider shrink-0">
          Simulate
        </span>

        {/* Variable select */}
        <select
          id="variable-select"
          value={activeVar}
          onChange={(e) => setSelectedVar(e.target.value)}
          className="rounded-lg border border-gray-200 bg-[#F5F5F7] px-3 py-2 text-sm text-[#2D3561] outline-none focus:border-[#2D3561]/30 cursor-pointer"
        >
          {driverNames.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </select>

        {/* Delta slider */}
        <div className="flex items-center gap-2">
          <input
            id="delta-slider"
            type="range"
            min={-50}
            max={50}
            step={5}
            value={delta}
            onChange={(e) => setDelta(Number(e.target.value))}
            className="w-36 accent-[#2D3561] cursor-pointer"
          />
          <span
            className={`w-12 text-right text-sm font-semibold ${
              delta > 0
                ? "text-[#22C55E]"
                : delta < 0
                  ? "text-[#EF4444]"
                  : "text-gray-400"
            }`}
          >
            {delta > 0 ? "+" : ""}
            {delta}%
          </span>
        </div>

        {/* Simulate button */}
        <button
          id="simulate-button"
          onClick={() => simulateMutation.mutate()}
          disabled={isSimulating}
          className="rounded-lg bg-[#2D3561] px-5 py-2 text-sm font-semibold text-white hover:bg-[#3a4578] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSimulating ? (
            <span className="inline-flex gap-0.5">
              <span className="animate-pulse">•</span>
              <span className="animate-pulse" style={{ animationDelay: "200ms" }}>•</span>
              <span className="animate-pulse" style={{ animationDelay: "400ms" }}>•</span>
            </span>
          ) : (
            "Simulate"
          )}
        </button>

        {/* Error message */}
        {simulateError && !simulation && (
          <span className="text-xs text-[#EF4444] ml-2">
            ⚠ {simulateError}
          </span>
        )}

        {/* Result badges */}
        <AnimatePresence mode="wait">
          {simulation && (
            <motion.div
              key={`${simulation.variable}-${simulation.delta}`}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="ml-auto flex items-center gap-2 flex-wrap"
            >
              {simulation.impacts.map((impact) => (
                <ResultBadge key={impact.variable} impact={impact} />
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.footer>
  );
}
