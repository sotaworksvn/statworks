import { create } from "zustand";
import type { ClerkUser, Column, InsightResult, SimulationResult } from "./types";

// ─── Store Shape ──────────────────────────────────────────────────────────────

interface AppState {
  // Auth
  user: ClerkUser | null;

  // Upload
  fileId: string | null;
  datasetName: string | null;
  rowCount: number | null;
  columns: Column[];
  isUploading: boolean;
  uploadProgress: number; // 0-100

  // Analysis
  insight: InsightResult | null;
  isAnalyzing: boolean;
  analyzeError: string | null;

  // Simulation
  simulation: SimulationResult | null;
  isSimulating: boolean;
  simulateError: string | null;
}

// ─── Actions ──────────────────────────────────────────────────────────────────

interface AppActions {
  setUser: (user: ClerkUser | null) => void;

  setUploadState: (state: {
    fileId: string;
    datasetName: string;
    rowCount: number;
    columns: Column[];
  }) => void;
  setIsUploading: (v: boolean) => void;
  setUploadProgress: (v: number) => void;

  setInsight: (insight: InsightResult | null) => void;
  setIsAnalyzing: (v: boolean) => void;
  setAnalyzeError: (err: string | null) => void;

  setSimulation: (sim: SimulationResult | null) => void;
  setIsSimulating: (v: boolean) => void;
  setSimulateError: (err: string | null) => void;

  /** Reset dataset and all derived state (insight, simulation) */
  resetDataset: () => void;
}

// ─── Initial State ────────────────────────────────────────────────────────────

const INITIAL_STATE: AppState = {
  user: null,
  fileId: null,
  datasetName: null,
  rowCount: null,
  columns: [],
  isUploading: false,
  uploadProgress: 0,
  insight: null,
  isAnalyzing: false,
  analyzeError: null,
  simulation: null,
  isSimulating: false,
  simulateError: null,
};

// ─── Zustand Store ────────────────────────────────────────────────────────────

export const useAppStore = create<AppState & AppActions>((set) => ({
  ...INITIAL_STATE,

  setUser: (user) => set({ user }),

  setUploadState: ({ fileId, datasetName, rowCount, columns }) =>
    set({
      fileId,
      datasetName,
      rowCount,
      columns,
      // Clear any previous analysis when a new dataset is loaded
      insight: null,
      simulation: null,
      analyzeError: null,
      simulateError: null,
    }),

  setIsUploading: (isUploading) => set({ isUploading }),
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),

  setInsight: (insight) => set({ insight }),
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setAnalyzeError: (analyzeError) => set({ analyzeError }),

  setSimulation: (simulation) => set({ simulation }),
  setIsSimulating: (isSimulating) => set({ isSimulating }),
  setSimulateError: (simulateError) => set({ simulateError }),

  resetDataset: () =>
    set({
      fileId: null,
      datasetName: null,
      rowCount: null,
      columns: [],
      insight: null,
      simulation: null,
      analyzeError: null,
      simulateError: null,
      isAnalyzing: false,
      isSimulating: false,
    }),
}));
