"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { ImpactResult } from "@/lib/types";

interface ResultBadgeProps {
  impact: ImpactResult;
}

export function ResultBadge({ impact }: ResultBadgeProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const target = impact.delta_pct;
  const isPositive = target >= 0;

  useEffect(() => {
    setDisplayValue(0);
    const duration = 800; // ms
    const steps = 40;
    const stepDuration = duration / steps;
    let current = 0;
    let step = 0;

    const timer = setInterval(() => {
      step++;
      // Ease-out: fast start, slow finish
      const progress = 1 - Math.pow(1 - step / steps, 3);
      current = target * progress;
      setDisplayValue(current);

      if (step >= steps) {
        setDisplayValue(target);
        clearInterval(timer);
      }
    }, stepDuration);

    return () => clearInterval(timer);
  }, [target]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.3 }}
      className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold ${
        isPositive
          ? "bg-[#22C55E]/10 text-[#16A34A]"
          : "bg-[#EF4444]/10 text-[#DC2626]"
      }`}
    >
      <span className="text-xs">{impact.variable}</span>
      <span>
        {isPositive ? "↑" : "↓"} {isPositive ? "+" : ""}
        {displayValue.toFixed(1)}%
      </span>
    </motion.div>
  );
}
