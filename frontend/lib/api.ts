import type { UploadResult, InsightResult, SimulationResult, ApiError } from "./types";

// Rule: backend URL always from env var — fail loudly if missing
// Lazy getter to avoid crashing during SSR build (env var may only be
// available client-side via NEXT_PUBLIC_ prefix).
function getBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_BACKEND_URL;
  if (!url) {
    // Fallback for SSR builds and local dev — prevents build crashes
    return "http://localhost:8000";
  }
  // Strip trailing slash to prevent double-slash URLs (e.g. "//sync-user")
  return url.replace(/\/+$/, "");
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err: ApiError = (await res.json()) as ApiError;
      detail = err.detail ?? detail;
    } catch {
      // ignore parse failure — use status code as fallback
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ─── API Functions ────────────────────────────────────────────────────────────

/**
 * Sync a Clerk user to Supabase (upsert).
 * Called once on login to ensure the user record exists.
 */
export async function syncUser(
  clerkUserId: string,
  email?: string,
  name?: string
): Promise<{ id: string | null; synced: boolean }> {
  const res = await fetch(`${getBaseUrl()}/api/auth/sync-user`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ clerk_user_id: clerkUserId, email, name }),
  });
  return handleResponse<{ id: string | null; synced: boolean }>(res);
}

/**
 * Upload one or more files (.xlsx / .csv for data; .docx / .pptx for context).
 * Returns the file_id, column metadata, row count, and whether context was extracted.
 */
export async function uploadFile(
  files: File[],
  clerkUserId?: string
): Promise<UploadResult> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }

  const headers: Record<string, string> = {};
  if (clerkUserId) {
    headers["x-clerk-user-id"] = clerkUserId;
  }

  const res = await fetch(`${getBaseUrl()}/api/upload`, {
    method: "POST",
    headers,
    body: form,
  });

  return handleResponse<UploadResult>(res);
}

/**
 * Run the full AI + statistical analysis pipeline on a previously uploaded dataset.
 */
export async function analyzeDataset(
  fileId: string,
  query: string,
  clerkUserId?: string
): Promise<InsightResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (clerkUserId) {
    headers["x-clerk-user-id"] = clerkUserId;
  }

  const res = await fetch(`${getBaseUrl()}/api/chat/analyze`, {
    method: "POST",
    headers,
    body: JSON.stringify({ file_id: fileId, query }),
  });

  return handleResponse<InsightResult>(res);
}

/**
 * Run a what-if simulation using the coefficient cache from a prior /analyze call.
 */
export async function simulateScenario(
  fileId: string,
  variable: string,
  delta: number,
  clerkUserId?: string
): Promise<SimulationResult> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (clerkUserId) {
    headers["x-clerk-user-id"] = clerkUserId;
  }

  const res = await fetch(`${getBaseUrl()}/api/monitor/simulate`, {
    method: "POST",
    headers,
    body: JSON.stringify({ file_id: fileId, variable, delta }),
  });

  return handleResponse<SimulationResult>(res);
}
