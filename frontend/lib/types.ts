// ─── Domain Types ─────────────────────────────────────────────────────────────

export interface ClerkUser {
  readonly id: string;
  readonly email: string | null;
  readonly firstName: string | null;
  readonly lastName: string | null;
  readonly imageUrl: string | null;
}

// ─── Navigation ───────────────────────────────────────────────────────────────

// "dashboard" removed — Monitor feature removed in EdTech track
export type ActiveView = "upload" | "chat" | "data-viewer" | "history";

// ─── Upload ───────────────────────────────────────────────────────────────────

export interface Column {
  readonly name: string;
  readonly dtype: string;
  readonly is_numeric: boolean;
}

export interface UploadResult {
  readonly file_id: string;
  readonly columns: readonly Column[];
  readonly row_count: number;
  readonly context_extracted: boolean;
}

export interface UploadedFile {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly content_hash: string | null;
  readonly uploaded_at: string;
  readonly columns: readonly Column[];
  readonly row_count: number;
}

// ─── Analysis ─────────────────────────────────────────────────────────────────

export interface DriverResult {
  readonly name: string;
  readonly coef: number;
  readonly p_value: number;
  readonly significant: boolean;
}

export interface DecisionTrace {
  readonly score_pls: number;
  readonly score_reg: number;
  readonly engine_selected: "regression" | "pls" | null;
  readonly reason: string;
}

// ─── Scholarship ──────────────────────────────────────────────────────────────

export interface SchoolMatch {
  readonly school_name: string;
  readonly country: string;
  readonly match_score: number;
  readonly match_level: "dream" | "target" | "safety";
  readonly strengths: readonly string[];
  readonly weaknesses: readonly string[];
}

export interface SimulationResult {
  readonly type: string;
  readonly school_name: string;
  readonly current_score: number;
  readonly new_score: number;
  readonly delta: number;
  readonly level_change: string | null;
}

export interface InsightResult {
  readonly summary: string;
  readonly drivers: readonly DriverResult[];
  readonly r2: number | null;
  readonly recommendation: string;
  readonly model_type: "regression" | "pls" | "scholarship_pls" | null;
  readonly decision_trace: DecisionTrace;
  readonly result_type?: "driver_analysis" | "scholarship_prediction" | string;
  readonly school_matches?: readonly SchoolMatch[];
  readonly student_profile?: Record<string, unknown>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  readonly table_data?: Record<string, any> | null;
  /** If intent was not driver_analysis */
  readonly not_supported?: boolean;
  readonly suggestion?: string;
}

// ─── Legacy Simulation (what-if for driver analysis) ─────────────────────────

export interface ImpactResult {
  readonly variable: string;
  readonly delta_pct: number;
}

export interface DriverSimulationResult {
  readonly variable: string;
  readonly delta: number;
  readonly impacts: readonly ImpactResult[];
}

// ─── Dataset Content (Data Viewer) ────────────────────────────────────────────

export interface DatasetContent {
  readonly file_id: string;
  readonly file_name: string | null;
  readonly file_type: string | null;
  readonly columns: readonly Column[];
  readonly rows: readonly Record<string, unknown>[];
  readonly row_count: number;
  readonly context_text: string | null;
}

// ─── API Error ────────────────────────────────────────────────────────────────

export interface ApiError {
  readonly detail: string;
}
