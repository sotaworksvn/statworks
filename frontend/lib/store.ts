import { create } from "zustand";
import type { ActiveView, ClerkUser, Column, InsightResult, SimulationResult, UploadedFile } from "./types";

// ─── Store Shape ──────────────────────────────────────────────────────────────

interface AppState {
  // Auth
  user: ClerkUser | null;

  // Navigation
  activeView: ActiveView;
  hasUploadedData: boolean;
  activeConversationId: string | null;

  // Upload
  fileId: string | null;
  datasetName: string | null;
  rowCount: number | null;
  columns: Column[];
  isUploading: boolean;
  uploadProgress: number; // 0-100
  uploadedFiles: UploadedFile[];
  localParsedData: Record<string, { columns: string[]; rows: Record<string, unknown>[] }>;

  // Analysis
  insight: InsightResult | null;
  isAnalyzing: boolean;
  analyzeError: string | null;
  chatMessages: { role: "user" | "assistant"; content: string }[];

  // Simulation
  simulation: SimulationResult | null;
  isSimulating: boolean;
  simulateError: string | null;
}

// ─── Actions ──────────────────────────────────────────────────────────────────

interface AppActions {
  setUser: (user: ClerkUser | null) => void;

  // Navigation
  setActiveView: (view: ActiveView) => void;
  setActiveConversationId: (id: string | null) => void;

  setUploadState: (state: {
    fileId: string;
    datasetName: string;
    rowCount: number;
    columns: Column[];
  }) => void;
  setIsUploading: (v: boolean) => void;
  setUploadProgress: (v: number) => void;
  addUploadedFile: (file: UploadedFile) => void;
  removeUploadedFile: (id: string) => void;
  setLocalParsedData: (id: string, data: { columns: string[]; rows: Record<string, unknown>[] }) => void;
  invalidateLocalData: (id: string) => void;

  setInsight: (insight: InsightResult | null) => void;
  setIsAnalyzing: (v: boolean) => void;
  setAnalyzeError: (err: string | null) => void;
  addChatMessage: (msg: { role: "user" | "assistant"; content: string }) => void;
  setChatMessages: (msgs: { role: "user" | "assistant"; content: string }[]) => void;

  setSimulation: (sim: SimulationResult | null) => void;
  setIsSimulating: (v: boolean) => void;
  setSimulateError: (err: string | null) => void;

  /** Reset dataset and all derived state (insight, simulation) */
  resetDataset: () => void;
}

// ─── Initial State ────────────────────────────────────────────────────────────

const INITIAL_STATE: AppState = {
  user: null,
  activeView: "upload",
  hasUploadedData: false,
  activeConversationId: null,
  fileId: null,
  datasetName: null,
  rowCount: null,
  columns: [],
  isUploading: false,
  uploadProgress: 0,
  uploadedFiles: [],
  localParsedData: {},
  insight: null,
  isAnalyzing: false,
  analyzeError: null,
  chatMessages: [],
  simulation: null,
  isSimulating: false,
  simulateError: null,
};

// ─── Zustand Store ────────────────────────────────────────────────────────────

export const useAppStore = create<AppState & AppActions>((set) => ({
  ...INITIAL_STATE,

  setUser: (user) => set({ user }),

  setActiveView: (activeView) => set({ activeView }),

  setActiveConversationId: (activeConversationId) => set({ activeConversationId }),

  setUploadState: ({ fileId, datasetName, rowCount, columns }) =>
    set({
      fileId,
      datasetName,
      rowCount,
      columns,
      hasUploadedData: true,
      activeView: "chat", // Switch to AI Chat after upload
      // Clear any previous analysis when a new dataset is loaded
      insight: null,
      simulation: null,
      analyzeError: null,
      simulateError: null,
    }),

  setIsUploading: (isUploading) => set({ isUploading }),
  setUploadProgress: (uploadProgress) => set({ uploadProgress }),

  addUploadedFile: (file) =>
    set((state) => ({
      uploadedFiles: [...state.uploadedFiles, file],
      hasUploadedData: true,
    })),

  removeUploadedFile: (id) =>
    set((state) => {
      const filtered = state.uploadedFiles.filter((f) => f.id !== id);
      const { [id]: _, ...restParsed } = state.localParsedData;
      return {
        uploadedFiles: filtered,
        localParsedData: restParsed,
        hasUploadedData: filtered.length > 0,
        ...(state.fileId === id ? { fileId: null, datasetName: null, rowCount: null, columns: [] } : {}),
      };
    }),

  setLocalParsedData: (id, data) =>
    set((state) => ({
      localParsedData: { ...state.localParsedData, [id]: data },
    })),

  invalidateLocalData: (id) =>
    set((state) => {
      const { [id]: _, ...rest } = state.localParsedData;
      return { localParsedData: rest };
    }),

  setInsight: (insight) => set({ insight }),
  setIsAnalyzing: (isAnalyzing) => set({ isAnalyzing }),
  setAnalyzeError: (analyzeError) => set({ analyzeError }),
  addChatMessage: (msg) => set((state) => ({ chatMessages: [...state.chatMessages, msg] })),
  setChatMessages: (chatMessages) => set({ chatMessages }),

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
