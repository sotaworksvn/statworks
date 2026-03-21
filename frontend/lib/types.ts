// ─── Domain Types ─────────────────────────────────────────────────────────────

export interface ClerkUser {
  readonly id: string;
  readonly email: string | null;
  readonly firstName: string | null;
  readonly lastName: string | null;
  readonly imageUrl: string | null;
}

// ─── Navigation ───────────────────────────────────────────────────────────────

export type ActiveView = "upload" | "chat" | "data-viewer" | "dashboard" | "history";

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
  readonly engine_selected: "regression" | "pls";
  readonly reason: string;
}

export interface InsightResult {
  readonly summary: string;
  readonly drivers: readonly DriverResult[];
  readonly r2: number | null;
  readonly recommendation: string;
  readonly model_type: "regression" | "pls" | null;
  readonly decision_trace: DecisionTrace;
  readonly result_type?: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  readonly table_data?: Record<string, any> | null;
  /** If intent was not driver_analysis */
  readonly not_supported?: boolean;
  readonly suggestion?: string;
}

// ─── Simulation ───────────────────────────────────────────────────────────────

export interface ImpactResult {
  readonly variable: string;
  readonly delta_pct: number;
}

export interface SimulationResult {
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
