# SOTA StatWorks — Task Plan

| Field            | Value                                               |
|------------------|-----------------------------------------------------|
| **Project**      | SOTA StatWorks                                      |
| **Team**         | Phú Nhuận Builder x SOTA Works                      |
| **Created**      | 2026-03-20                                          |
| **Last updated** | 2026-03-20                                          |
| **Build order**  | Phase 1: Backend → Phase 2: AI/LLM → Phase 3: Frontend |
| **Source docs**  | `01-prd.md` · `02-system-design.md` · `03-features-spec.md` · `04-rule.md` |

---

## Build Order Rationale

```
Phase 1 — Backend Core (no LLM)
  ↓ statistical engines + endpoints work independently
Phase 2 — AI / LLM Integration
  ↓ LLM layer wraps the already-tested backend
Phase 3 — Frontend
  ↓ landing page first, then app screen
  ↓ all API calls hit a fully working backend
```

The backend is built first so that the statistical core can be tested and validated with known datasets before any frontend or LLM work begins. The AI layer is added second so that the full `/analyze` pipeline can be verified end-to-end over HTTP before the frontend is wired. The frontend is built last, starting with the landing page, then the single-screen app.

---

## Status Legend

| Symbol | Meaning |
|---|---|
| `[ ]` | Not started |
| `[~]` | In progress |
| `[x]` | Done |
| `[!]` | Blocked / needs decision |

---

---

# Phase 1 — Backend Core

> **Goal:** A fully working FastAPI server with all three endpoints (`/health`, `/upload`, `/analyze-stub`, `/simulate`) returning correct responses — without any LLM involvement. The `/analyze` endpoint at this stage returns hardcoded or heuristic-only results.
>
> **Rule references:** `04-rule.md` §Common–API, §Python–General, §Python–FastAPI, §Python–Statistical Engine, §Python–Data Ingestion

---

## 1.1 — Project Scaffold

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.1.1** Create backend directory `backend/` at project root. | — | Directory exists |
| `[ ]` | **1.1.2** Create `pyproject.toml` with Python `>=3.11` requirement and all production dependencies: `fastapi`, `uvicorn[standard]`, `pydantic`, `numpy`, `scipy`, `pandas`, `openpyxl`, `python-docx`, `python-pptx`, `openai`. | Python–General: Python 3.11+ | `pip install -e .` succeeds |
| `[ ]` | **1.1.3** Create `backend/main.py` with a bare FastAPI app instance. Add CORS middleware with `allow_origins=["*"]` (development mode). | Security: CORS open in dev only | Server starts with `uvicorn backend.main:app --reload` |
| `[ ]` | **1.1.4** Implement `GET /health` returning `{ "status": "ok" }` with HTTP 200. | Common–API: health endpoint mandatory | `curl /health` → 200 `{"status":"ok"}` |
| `[ ]` | **1.1.5** Create the in-memory file store: `file_store: OrderedDict` with a module-level `asyncio.Lock`. Implement `get_entry`, `set_entry` helpers that enforce the 10-entry LRU cap. | Performance: store ≤10 entries LRU; FastAPI: asyncio.Lock | Inserting 11 entries evicts the oldest |

---

## 1.2 — Data Ingestion (F-01 · `POST /upload`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.2.1** Define Pydantic response model `UploadResponse` with fields: `file_id: str`, `columns: list[ColumnMeta]`, `row_count: int`, `context_extracted: bool`. Define `ColumnMeta` with `name: str`, `dtype: str`, `is_numeric: bool`. | FastAPI: all responses typed | Model validates correctly |
| `[ ]` | **1.2.2** Implement file extension detection helper. Allowlist: `{.xlsx, .csv, .docx, .pptx}`. Return HTTP 415 for unsupported types. | Security: validate before parsing; Common–API: HTTP 415 | `.pdf` upload → 415 |
| `[ ]` | **1.2.3** Implement file size check. Reject files > 10 MB with HTTP 413 before calling any parser. | Security: size check first; Performance: 10 MB limit | 15 MB file → 413 |
| `[ ]` | **1.2.4** Enforce exactly one primary file (`.xlsx` or `.csv`) per request. Return HTTP 422 if multiple primary files are submitted. | Security: FR-01-04; Common–API: HTTP 422 | Two `.xlsx` → 422 |
| `[ ]` | **1.2.5** Implement Excel / CSV parser: `pandas.read_excel` (openpyxl engine) for `.xlsx`; `pandas.read_csv` for `.csv`. Strip column name whitespace (`df.columns.str.strip()`). Do NOT lowercase. | Data Ingestion: strip not lowercase | Column `" Trust "` → `"Trust"` |
| `[ ]` | **1.2.6** Implement dtype detection: mark a column `is_numeric=True` if `pandas.api.types.is_numeric_dtype`. | F-01 FR-01-11 | Mixed column list accurately flagged |
| `[ ]` | **1.2.7** Implement Word / PowerPoint text extractor functions. `.docx`: iterate `doc.paragraphs`, extract `.text`. `.pptx`: iterate slides → shapes → text frames, extract `.text`. Join with `"\n"`. Never extract images. | Data Ingestion: plain text only | `.pptx` with images → only text extracted |
| `[ ]` | **1.2.8** Implement `POST /upload` handler: detect types → size check → primary count check → parse primary → parse context → generate `file_id = str(uuid.uuid4())` → store entry → return `UploadResponse`. | FastAPI: async def; Security: validate before parsing | Full upload flow returns correct metadata |
| `[ ]` | **1.2.9** Test F-01: valid `.xlsx` upload, valid `.csv` + `.docx` combo, oversized file, unsupported format, two primary files. | F-01 Acceptance Criteria | All 5 test cases pass |

---

## 1.3 — Regression Engine

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.3.1** Create `backend/engines/regression.py`. Implement `compute_ols(df: pd.DataFrame, features: list[str], target: str, n_bootstrap: int = 200) -> RegressionResult`. | Statistical Engine; Python: lstsq not inv | Function is importable |
| `[ ]` | **1.3.2** OLS point estimate: use `np.linalg.lstsq(X, y, rcond=None)` where `X = df[features].values` (with intercept column prepended) and `y = df[target].values`. Extract coefficients β. | Python–General: lstsq mandatory | β shape matches `len(features)` |
| `[ ]` | **1.3.3** Compute R²: `1 - SS_res / SS_tot` using numpy arrays. Return `r2: float`. | F-02 FR-02-10 | R² = 1.0 for perfect fit test dataset |
| `[ ]` | **1.3.4** Bootstrap p-values: `rng = np.random.default_rng(seed=42)`. For each of `n_bootstrap` iterations, sample with replacement, recompute β, collect distribution. Estimate p-value as fraction of bootstrap β with opposite sign from point estimate. | Statistical Engine: fixed seed 42; Performance: ≤200 samples | Reproducible p-values on same dataset |
| `[ ]` | **1.3.5** Define `DriverResult(name: str, coef: float, p_value: float, significant: bool)` where `significant = p_value < 0.05`. Define `RegressionResult(drivers: list[DriverResult], r2: float, model_type: Literal["regression"])`. | F-02 Data Model | Dataclass validates |
| `[ ]` | **1.3.6** Sort drivers by `abs(coef)` descending, return top 5 only. | F-02 FR-02-12 | 10-feature dataset → 5 drivers returned |

---

## 1.4 — PLS Engine

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.4.1** Create `backend/engines/pls.py`. Implement `compute_pls(df: pd.DataFrame, indicator_groups: dict[str, list[str]], target: str, n_bootstrap: int = 200) -> PLSResult`. | Statistical Engine | Function importable |
| `[ ]` | **1.4.2** Compute latent variable scores: for each group, `LV = df[indicators].mean(axis=1)`. Do NOT implement NIPALS or iterative PLS. | Statistical Engine: mean-LV only | LV values are row-wise means |
| `[ ]` | **1.4.3** Build the inner model DataFrame from computed LV columns. Run OLS on it (reuse regression engine). | F-02 FR-02-11 | Path coefficients computed |
| `[ ]` | **1.4.4** Bootstrap path coefficients with `seed=42`. Return `PLSResult` with `drivers`, `r2`, `model_type="pls"`. | Statistical Engine: fixed seed 42 | Reproducible on rerun |
| `[ ]` | **1.4.5** Wrap PLS engine call in try/except. On any exception (singular matrix, insufficient rows), raise a custom `PLSFallbackError`. The caller (Decision Router) catches this and falls back to OLS. | Error Handling: Layer 2 fallback | Underdetermined dataset triggers fallback |

---

## 1.5 — Decision Router

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.5.1** Create `backend/router.py`. Implement `score_model(df, features, target) -> tuple[float, float, str, str]` returning `(score_pls, score_reg, engine, reason)`. | F-02 FR-02-08/09 | Returns a tuple |
| `[ ]` | **1.5.2** Compute `L` (latent variable presence): 1 if at least one feature has multiple highly-correlated sub-columns (Pearson r > 0.6), else 0. | Decision Router scoring | L=0 for uncorrelated features |
| `[ ]` | **1.5.3** Compute `M` (multiplicity): number of features / 10, capped at 1.0. | Decision Router scoring | M=0.5 for 5 features |
| `[ ]` | **1.5.4** Compute `C` (complexity): 1 if `len(features) > 3 and L > 0`, else 0. | Decision Router scoring | C reflects structural complexity |
| `[ ]` | **1.5.5** Compute `O` (observability): fraction of features that are numeric (is_numeric count / total). | Decision Router scoring | O=1.0 for all-numeric dataset |
| `[ ]` | **1.5.6** Apply formulas: `score_pls = 0.4*L + 0.3*M + 0.3*C`; `score_reg = 0.6*O + 0.4*(1-C)`. Select PLS if `score_pls > score_reg`, else regression. Compose human-readable `reason` string. | F-02 FR-02-08/09 | Pure numeric dataset → regression selected |
| `[ ]` | **1.5.7** Return `DecisionTrace(score_pls, score_reg, engine_selected, reason)` as a Pydantic model. | F-02 FR-02-14; Statistical Engine: trace always returned | Trace non-null in all cases |

---

## 1.6 — Validation Layer

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.6.1** Create `backend/validation.py`. Implement `validate_parsed_intent(parsed: dict, df: pd.DataFrame) -> CleanedIntent`. | Security: LLM output through validation; F-02 FR-02-05/06/07 | Function importable |
| `[ ]` | **1.6.2** Strip features: remove any name in `parsed["features"]` not in `df.columns.tolist()`. | F-02 FR-02-05 | Hallucinated column name removed |
| `[ ]` | **1.6.3** Auto-detect target: if `parsed["target"]` is missing or not in columns, select the last column, then fallback to any column containing "index", "score", or "rate". | F-02 FR-02-06 | Missing target → last column selected |
| `[ ]` | **1.6.4** Auto-select features: if `parsed["features"]` is empty after stripping, select all numeric columns minus the target. | F-02 FR-02-07 | Empty features → all numeric columns |
| `[ ]` | **1.6.5** Define `CleanedIntent(intent: str, target: str, features: list[str])` Pydantic model. | FastAPI: Pydantic for all models | Model validates |

---

## 1.7 — Simulation Engine (F-03 · `POST /simulate`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.7.1** Create `backend/engines/simulation.py`. Implement `build_graph(coefficient_cache: dict) -> dict[str, list[tuple[str, float]]]`. | F-03 FR-03-05 | Graph correctly mirrors cache |
| `[ ]` | **1.7.2** Implement `dfs_propagate(graph, start_var, delta, visited=None) -> dict[str, float]`. Use a `visited: set` to prevent cycles. Accumulate `ΔY = β * ΔX` (direct) and multi-hop impacts recursively. | Common–Error: DFS cycle detection mandatory; F-03 FR-03-06 | Cycle graph terminates; multi-hop correctly accumulated |
| `[ ]` | **1.7.3** Define `SimulationResponse(variable: str, delta: float, impacts: list[ImpactResult])` where `ImpactResult(variable: str, delta_pct: float)`. Round `delta_pct` to 1 decimal place. Exclude the input variable from impacts list. | F-03 FR-03-07/08 | Response shape correct |
| `[ ]` | **1.7.4** Define `SimulateRequest(file_id: str, variable: str, delta: float)` Pydantic model. | FastAPI: Pydantic for all bodies | Model validates |
| `[ ]` | **1.7.5** Implement `POST /simulate` handler: lookup `file_id` (404 if missing) → check `coefficient_cache` exists (409 if None) → validate `variable` in cache keys (422 with valid list) → build graph → DFS propagate → return `SimulationResponse`. | F-03 FR-03-01/02/03/04; Performance: /simulate never re-runs model | All 4 F-03 acceptance criteria pass |
| `[ ]` | **1.7.6** Wrap handler in top-level try/except. Return HTTP 500 JSON on unexpected failure. | Common–Error: unhandled exception → structured 500 | RuntimeError in DFS → 500 JSON body |

---

## 1.8 — Stub `/analyze` Endpoint (heuristic-only, no LLM)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.8.1** Define `AnalyzeRequest(file_id: str, query: str)` and `AnalyzeResponse` Pydantic models matching the full F-02 response shape. | FastAPI: Pydantic models | Models validate |
| `[ ]` | **1.8.2** Implement a stub `POST /analyze` that: looks up `file_id` (404 if missing) → selects all numeric columns as features, last column as target → runs Decision Router → runs statistical engine → stores `coefficient_cache` → returns a template-generated `summary` and `recommendation` (no LLM). | F-02 §4.1 happy path (without LLM calls 1 and 2) | Stub returns valid AnalyzeResponse for known dataset |
| `[ ]` | **1.8.3** Verify full backend smoke test: upload a dataset, call stub `/analyze`, call `/simulate`. All three return 200 with correct shapes. | F-01/F-02/F-03 Acceptance Criteria | End-to-end backend smoke test passes |

---

## 1.9 — Backend Configuration & Deployment Prep

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **1.9.1** Create `backend/config.py`. Read `OPENAI_API_KEY_1` through `OPENAI_API_KEY_4` and `CORS_ORIGIN` from `os.environ`. Fail loudly at import time if required vars are missing in non-development mode. | Security: API keys in env vars only | Missing key → `ValueError` with descriptive message |
| `[ ]` | **1.9.2** Create `render.yaml` (or configure via Render dashboard): service type = Web Service, build command = `pip install -e .`, start command = `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. | Git & Deployment | Render deploy succeeds |
| `[ ]` | **1.9.3** Add `.gitignore` at project root: `__pycache__/`, `*.pyc`, `.env`, `.env.local`, `node_modules/`, `.next/`, `dist/`. | Git & Deployment | gitignore file committed |
| `[ ]` | **1.9.4** Deploy backend to Render.com and verify `GET /health` returns 200 on the live URL. | Git & Deployment; Common–API: health endpoint | Live URL `/health` → 200 |

---

---

# Phase 2 — AI / LLM Integration

> **Goal:** Replace the stub `/analyze` with the full 2-call LLM pipeline using `gpt-5.4-mini` (Call 1) and `gpt-5.4` (Call 2). The fallback chain from §6.4 of the System Design is fully implemented.
>
> **Rule references:** `04-rule.md` §Python–AI/LLM Layer; System Design §4.2; Feature Spec F-02

---

## 2.1 — OpenAI SDK Setup & Key Rotation

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **2.1.1** Create `backend/llm/client.py`. Import `AsyncOpenAI` from `openai`. Initialise 4 client instances from env vars `OPENAI_API_KEY_1` through `OPENAI_API_KEY_4`. Store in a list `clients: list[AsyncOpenAI]`. | AI/LLM: openai SDK only; Security: keys in env vars | 4 clients initialised without error |
| `[ ]` | **2.1.2** Implement `get_active_client() -> AsyncOpenAI` that returns `clients[0]` (primary). On `RateLimitError`, rotate to the next key in the list (round-robin through indices). Implement as a module-level rotating index. | AI/LLM: key rotation order fixed | Mocked RateLimitError → rotates to key 2 |
| `[ ]` | **2.1.3** Implement `call_llm_with_retry(client, **kwargs) -> dict` that: attempts LLM call → on failure, sleeps 0.5s → retries up to 2 more times → raises `LLMFailureError` after 3 total attempts. | AI/LLM: retry ×2 only; Error Handling: Layer 1 | 3 consecutive failures → LLMFailureError raised |

---

## 2.2 — LLM Call 1: Intent Parsing (`gpt-5.4-mini`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **2.2.1** Create `backend/llm/parser.py`. Define `SYSTEM_PROMPT_PARSE` as a module-level constant containing the strict JSON schema and instructions. Schema: `{"intent": "...", "target": "...", "features": [...]}`. Allowed intents: `driver_analysis`, `summary`, `comparison`. | AI/LLM: system prompt must enforce schema; Call 1 uses gpt-5.4-mini | Prompt is a non-empty string constant |
| `[ ]` | **2.2.2** Implement `parse_user_intent(query: str, column_names: list[str], context_text: str | None, client: AsyncOpenAI) -> dict`. Build user prompt: list column names, append first 500 chars of `context_text` if present, append the user query. | AI/LLM: token budget ≤1000 | User prompt under 1000 tokens for typical dataset |
| `[ ]` | **2.2.3** Call OpenAI with `model="gpt-5.4-mini"` and `response_format={"type": "json_object"}`. Parse `response.choices[0].message.content` as JSON. | AI/LLM: gpt-5.4-mini for Call 1 only; JSON mode | Structured JSON returned |
| `[ ]` | **2.2.4** On `LLMFailureError`, return a default dict `{"intent": "driver_analysis", "target": None, "features": []}` to trigger the Validation Layer fallback. | Error Handling: Layer 1 fallback | LLM failure → default dict returned, pipeline continues |

---

## 2.3 — LLM Call 2: Insight Generation (`gpt-5.4`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **2.3.1** Create `backend/llm/insight.py`. Define `SYSTEM_PROMPT_INSIGHT` instructing the model to explain statistical results in plain business language. Include explicit instructions: "Do not use the words: coefficient, p-value, regression, PLS, OLS, bootstrap, latent variable." | AI/LLM: gpt-5.4 for Call 2 only; UX: no jargon | Prompt is a non-empty string constant |
| `[ ]` | **2.3.2** Implement `generate_insight(drivers: list[DriverResult], r2: float, target: str, model_type: str, client: AsyncOpenAI) -> InsightText`. Build user prompt with top driver names and coefficients (NOT raw JSON — natural language summary). Keep under 500 tokens. | AI/LLM: token budget ≤1000 | Insight prompt under 500 tokens |
| `[ ]` | **2.3.3** Call OpenAI with `model="gpt-5.4"`. Return `InsightText(summary: str, recommendation: str)` parsed from the response. | AI/LLM: gpt-5.4 for Call 2 | Non-empty summary and recommendation |
| `[ ]` | **2.3.4** On `LLMFailureError`, return the template fallback: `summary = f"{top_driver.name} shows the strongest relationship with {target} (β={top_driver.coef:.2f})."` and `recommendation = f"Focus on improving {top_driver.name} to drive better {target} outcomes."` | Error Handling: Layer 4 fallback | LLM failure → template strings returned |

---

## 2.4 — Full `/analyze` Pipeline Assembly

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **2.4.1** Replace the stub `/analyze` handler with the full pipeline. Wrap the entire handler body in a top-level `try/except` returning HTTP 500 on unexpected failure. | Error Handling: top-level try/except mandatory | RuntimeError inside handler → 500 JSON |
| `[ ]` | **2.4.2** Step 1 in handler: lookup `file_id` → 404 if missing. | F-02 FR-02-02 | Unknown file_id → 404 |
| `[ ]` | **2.4.3** Step 2: Call `parse_user_intent` (LLM Call 1). Pass result to `validate_parsed_intent`. The handler never touches raw LLM output directly. | Security: LLM output through Validation Layer | Raw LLM output never reaches engine |
| `[ ]` | **2.4.4** Step 3 — Intent gate: if `cleaned.intent != "driver_analysis"`, return `{ "not_supported": true, "suggestion": "Ask what drives [target], e.g. 'What affects retention?'" }` with HTTP 200. | F-02 FR-02-04 | Unsupported intent returns structured 200 |
| `[ ]` | **2.4.5** Step 4: Call Decision Router → get `engine`, `trace`. | 1.5.x tasks complete | Trace populated |
| `[ ]` | **2.4.6** Step 5: Call selected engine. On `PLSFallbackError`, fall back to OLS, update `trace.reason`. On OLS failure, return Layer 3 response. | Error Handling: 4-layer chain; Statistical Engine: trace always returned | PLS failure → OLS executed; trace updated |
| `[ ]` | **2.4.7** Step 6: Store `coefficient_cache` under `file_id` in the in-memory store. | F-02 FR-02-15 | `/simulate` succeeds immediately after `/analyze` |
| `[ ]` | **2.4.8** Step 7: Call `generate_insight` (LLM Call 2). | AI/LLM: ≤2 calls per request | Exactly 2 LLM calls in OpenAI dashboard log |
| `[ ]` | **2.4.9** Step 8: Assemble and return full `AnalyzeResponse` including `decision_trace`. | F-02 FR-02-14; Statistical Engine: trace always returned | All required fields present in response |
| `[ ]` | **2.4.10** Measure total handler wall-clock time in development. Ensure < 2s for a 120-row, 5-feature dataset. If budget is exceeded, reduce bootstrap to 100 or trim prompts. | Performance: <2s enforce at handler level | Timing log confirms < 2s |

---

## 2.5 — End-to-End AI Pipeline Verification

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **2.5.1** Run the full pipeline with the prepared demo dataset: upload → analyze → simulate. Verify `summary` and `recommendation` are business-language (no jargon). | AI/LLM layer; UX: no jargon | Output contains no: "coefficient", "p-value", "OLS", "PLS", "regression" |
| `[ ]` | **2.5.2** Test adversarial query: submit a query with a hallucinated column name. Verify the Validation Layer strips it and the pipeline still returns a valid response. | Security: Validation Layer is gatekeeper | Valid response despite hallucinated column |
| `[ ]` | **2.5.3** Test LLM offline simulation: mock `call_llm_with_retry` to always raise. Verify all 4 fallback layers produce a valid `AnalyzeResponse`. | Error Handling: 4-layer chain; NFR-02-06: 100% valid response | All 4 fallback scenarios return 200 with body |
| `[ ]` | **2.5.4** Redeploy to Render.com with all `OPENAI_API_KEY_*` env vars set. Verify live end-to-end call. | Git & Deployment | Live `/analyze` returns insight with gpt-5.4 narrative |

---

---

# Phase 3 — Frontend

> **Goal:** A Next.js 14 app deployed to Vercel. Starts with a marketing landing page ("Launch to App" button) giving judges/mentors all project context at a glance, then the single-screen decision interface with Chat, Insight, and Simulation panels.
>
> **Rule references:** `04-rule.md` §TypeScript, §React/Next.js; Feature Spec F-04; PRD §4 User Needs

---

## 3.1 — Project Scaffold

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.1.1** Create Next.js 14 app in `frontend/` using App Router with TypeScript: `npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir`. | SD §3 Tech Stack | `npm run dev` starts without errors |
| `[ ]` | **3.1.2** Install additional dependencies: `framer-motion`, `recharts`, `zustand`, `@tanstack/react-query`, `react-dropzone`, `@shadcn/ui` (init with `npx shadcn-ui@latest init`). | SD §3 Tech Stack | `npm install` succeeds; no peer dependency errors |
| `[ ]` | **3.1.3** Create `frontend/.env.local` with `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000`. Add `.env.local` to `.gitignore`. Set the production Render URL in Vercel dashboard environment variables. | Git & Deployment; API Layer: NEXT_PUBLIC_BACKEND_URL mandatory | Env var readable via `process.env.NEXT_PUBLIC_BACKEND_URL` |
| `[ ]` | **3.1.4** Create `frontend/lib/api.ts`. Implement three typed async functions: `uploadFile(files: File[]) → Promise<UploadResult>`, `analyzeDataset(fileId: string, query: string) → Promise<InsightResult>`, `simulateScenario(fileId: string, variable: string, delta: number) → Promise<SimulationResult>`. Each reads `NEXT_PUBLIC_BACKEND_URL` or throws. | API Layer: backend URL via env var; API Layer: typed functions only | TypeScript compiles; functions importable |
| `[ ]` | **3.1.5** Create `frontend/lib/store.ts`. Define and export the Zustand store with all fields: `fileId`, `datasetName`, `rowCount`, `columns`, `insight`, `simulation`, `isAnalyzing`, `isSimulating`, `analyzeError`, `simulateError`. | State Management: Zustand for UI state | Store importable; initial state is nulls |
| `[ ]` | **3.1.6** Define all TypeScript interfaces in `frontend/lib/types.ts`: `UploadResult`, `Column`, `InsightResult`, `DriverResult`, `DecisionTrace`, `SimulationResult`, `ImpactResult`. All must be `readonly` where applicable. | TypeScript: all API responses explicitly typed | All interfaces compile; no `any` |
| `[ ]` | **3.1.7** Wrap `app/layout.tsx` with `QueryClientProvider` (React Query). | State Management: React Query for server state | Provider wraps the app |

---

## 3.2 — Landing Page (`app/page.tsx`)

> The landing page is the **first thing judges, mentors, and organizers see**. It must communicate the entire project in under 30 seconds and provide a single prominent CTA: **"Launch to App"**.

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.2.1** Create `app/page.tsx` as the landing page. This file replaces the default Next.js home page. `app/app/page.tsx` will be the actual application screen. | F-04: one screen paradigm (app at `/app`); landing at `/` | Both routes resolve |
| `[ ]` | **3.2.2** Implement **Hero section**: large bold headline `"From Data to Decisions — Instantly."`, one-liner subheadline `"SOTA StatWorks is an AI-powered decision engine that turns raw data into ranked insights and simulations — without statistical expertise."`, and a prominent `"🚀 Launch to App"` button linking to `/app`. | PRD Appendix: product identity; Notice 3 | CTA button navigates to `/app` |
| `[ ]` | **3.2.3** Implement **Problem section**: three pain-point cards with icons — (1) "Tools are too complex" (SPSS/SmartPLS), (2) "Output ≠ Decision" (numbers without meaning), (3) "No simulation" (can't answer what-if). | PRD §1 Problem | Section renders correctly |
| `[ ]` | **3.2.4** Implement **Solution section**: three capability tiles — (1) "Ask Anything" (natural language), (2) "Auto Statistical Modeling" (AI selects OLS or PLS-SEM), (3) "Simulate Decisions" (slider → instant forecast). | PRD §2 Solution | Section renders correctly |
| `[ ]` | **3.2.5** Implement **How It Works section**: 5-step numbered flow — Upload data → Ask a question → AI selects model → Get insight → Simulate changes. Animate steps with Framer Motion stagger. | PRD §8 How It Works | Steps render with stagger animation |
| `[ ]` | **3.2.6** Implement **vs. Competitors section**: side-by-side comparison table — SOTA StatWorks vs. SPSS vs. SmartPLS vs. Generic AI. Highlight green checkmarks for SOTA StatWorks wins. | PRD §5 Differentiation | Table renders; mobile-readable |
| `[ ]` | **3.2.7** Implement **Tech Stack section** (for technical judges): logos/badges for FastAPI, Next.js, OpenAI `gpt-5.4-mini` + `gpt-5.4`, numpy/scipy, Vercel, Render. Brief one-line description per item. | SD §3 Tech Stack | Section renders without broken images |
| `[ ]` | **3.2.8** Implement **Team section**: team name "Phú Nhuận Builder x SOTA Works". Include project name, hackathon context. | PRD header: team name | Section renders |
| `[ ]` | **3.2.9** Implement **Footer**: repeat `"🚀 Launch to App"` CTA, tagline, team name. | Landing page completeness | Second CTA navigates to `/app` |
| `[ ]` | **3.2.10** Apply polished visual design: dark or deep-blue background, gradient headline text, card hover effects, smooth scroll between sections. Use Google Font (Inter or Outfit) via `next/font`. | PRD design: wow first impression | Lighthouse Performance ≥80; no layout shift |
| `[ ]` | **3.2.11** Set `<title>` and `<meta name="description">` in `app/layout.tsx`: `title = "SOTA StatWorks — From Data to Decisions, Instantly"`, `description = "AI-powered statistical decision engine..."`. | SEO best practices | Meta tags present in page source |

---

## 3.3 — App Shell (`app/app/page.tsx`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.3.1** Create `app/app/page.tsx` (the single-screen app). Create `app/app/layout.tsx` that wraps only app routes (not landing page). | Component Design: one page = one screen | Route `/app` resolves |
| `[ ]` | **3.3.2** Implement `<AppLayout>` component. Two-column main area (30% chat, 70% insight), sticky simulation bar at the bottom, header at top. Use CSS Grid or Flex. | SD §4.5 Component Tree; F-04 FR-04-03/15 | Layout renders at 1280px viewport |
| `[ ]` | **3.3.3** Implement `<Header>` component. Displays: "SOTA StatWorks" logo/wordmark (left), dataset name badge + row count (centre, shown after upload), upload/replace button (right). | F-04 FR-04-23 | Badge shows `"survey.xlsx · 120 rows"` after upload |

---

## 3.4 — Upload & Drop Zone

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.4.1** Implement `<UploadZone>` using `react-dropzone`. Show when `fileId == null` in the Zustand store. Accept `.xlsx`, `.csv`, `.docx`, `.pptx`. Display allowed formats and 10 MB limit. | F-04 FR-04-01/02 | Drop zone renders on fresh load |
| `[ ]` | **3.4.2** On file drop/select, call `uploadFile()` from `lib/api.ts`. On success, write `fileId`, `datasetName`, `rowCount`, `columns` to Zustand store. Replace upload zone with chat panel. | F-04 FR-04-03; API Layer: typed functions | Store updates; chat panel appears |
| `[ ]` | **3.4.3** On upload failure, display a visible error toast with the API `detail` message. | F-04 FR-04-04; API Layer: all errors visible | Error toast appears for 415 response |

---

## 3.5 — Chat Panel (`<ChatPanel>`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.5.1** Implement `<ChatPanel>` component containing `<MessageList>`, `<SuggestedPrompts>`, and `<InputBox>`. | SD §4.5; F-04 FR-04-05 | Component renders |
| `[ ]` | **3.5.2** Implement `<SuggestedPrompts>`: display 3 clickable prompt chips when `messages.length === 0`. Hide permanently once the first message is submitted. Prompts: *"What affects retention?"*, *"Which factor has the biggest impact?"*, *"What drives customer trust?"* | F-04 FR-04-06/07; UX: suggested prompts disappear after first query | Prompts hidden after first submit |
| `[ ]` | **3.5.3** Implement `<InputBox>`: controlled text input + send button. On submit: append user message to `MessageList`, set `isAnalyzing = true` in Zustand, call `analyzeDataset()` React Query mutation. | F-04 FR-04-05/08/09 | Submit triggers mutation |
| `[ ]` | **3.5.4** On `/analyze` success: write `InsightResult` to Zustand `insight` field. Set `isAnalyzing = false`. Scroll chat to bottom. | State Management: server data to React Query, insight to Zustand | Store updates on success |
| `[ ]` | **3.5.5** On `/analyze` error: set `analyzeError` in Zustand. Display error message in chat area. | API Layer: all errors produce visible UI state | Error message appears in chat |
| `[ ]` | **3.5.6** Guard: if user interacts with input when `fileId == null`, show banner *"Upload a dataset to start."* | F-04 FR-04-21 | Banner appears when no file loaded |

---

## 3.6 — Insight Panel (`<InsightPanel>`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.6.1** Implement `<InsightPanel>` component. Reads `insight` and `isAnalyzing` from Zustand. Renders skeleton when `isAnalyzing = true`. | F-04 FR-04-08 | Skeleton appears during loading |
| `[ ]` | **3.6.2** Implement `<SummaryCard>`: renders `insight.summary` as large bold text (1–2 lines). Animate with Framer Motion `initial={{ opacity: 0 }} animate={{ opacity: 1 }}` at 0ms delay. | F-04 FR-04-10/14; UX: progressive reveal order | SummaryCard fades in first |
| `[ ]` | **3.6.3** Implement `<DriverChart>` using Recharts `<BarChart layout="vertical">`. One bar per driver, sorted by `abs(coef)` desc. Bar color: green if `coef > 0`, red if `coef < 0`. Tooltip shows `{ coef, p_value, significant }`. Animate bars growing with Framer Motion `initial={{ width: 0 }}` at 200ms delay. | F-04 FR-04-11/14; UX: progressive reveal | Bars animate at 200ms offset; tooltip shows stats |
| `[ ]` | **3.6.4** Implement `<RecommendationCard>`: renders `insight.recommendation` in a visually distinct card (accent color background). MUST be visible without scrolling at 1280px viewport. | F-04 FR-04-12; Component Design: recommendation always visible | No scroll needed to see card |
| `[ ]` | **3.6.5** Apply Framer Motion fade-in to `<RecommendationCard>` at 400ms delay. | F-04 FR-04-14; UX: progressive reveal | RecommendationCard appears third |
| `[ ]` | **3.6.6** Implement `<ModelInfoCollapse>`: collapsed by default. Uses Shadcn/UI `<Collapsible>`. Content: `Model: {model_type}`, `R²: {r2}`, `Why this model: {decision_trace.reason}`. | F-04 FR-04-13 | Panel collapsed by default; expands on click |
| `[ ]` | **3.6.7** Enforce jargon ban: audit all JSX in InsightPanel. Remove any occurrence of: `coefficient`, `p-value`, `β`, `R²`, `OLS`, `PLS`, `SEM`, `regression`, `bootstrap`, `latent variable` from the default visible view. Move to `<ModelInfoCollapse>` only. | UX: no jargon in default view | No jargon visible without expanding collapse |
| `[ ]` | **3.6.8** Implement empty state: if `insight.drivers.length === 0`, display *"We couldn't find strong drivers. Try a different question or check your dataset."* | F-04 FR-04-22 | Empty drivers list → message shown |

---

## 3.7 — Simulation Bar (`<SimulationBar>`)

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.7.1** Implement `<SimulationBar>` as a fixed-bottom sticky bar. Only visible when `insight !== null`. Initially hidden. | F-04 FR-04-15 | Bar hidden before first insight; appears after |
| `[ ]` | **3.7.2** Implement `<VariableSelect>` using Shadcn/UI `<Select>`. Options = `insight.drivers.map(d => d.name)`. Controlled by local state. `id="variable-select"`. | F-04 FR-04-16; Component Design: unique IDs | Dropdown lists driver names |
| `[ ]` | **3.7.3** Implement `<DeltaSlider>`: range −50 to +50, step 5, default 20. Display current value with `%` suffix. `id="delta-slider"`. | F-04 FR-04-17; Component Design: unique IDs | Slider moves in 5% increments |
| `[ ]` | **3.7.4** Implement `<SimulateButton>`: calls `simulateScenario()` React Query mutation on click. Shows spinner while `isSimulating = true`. `id="simulate-button"`. | F-04 FR-04-18; Component Design: unique IDs | Button disabled during load; spinner shown |
| `[ ]` | **3.7.5** On `/simulate` success: write `SimulationResult` to Zustand. Render `<ResultBadge>` for each impact. | F-04 FR-04-19 | Badge appears for each impact |
| `[ ]` | **3.7.6** Implement count-up animation on `<ResultBadge>`: use Framer Motion `useSpring` or a `useEffect` counter hook. Animate from `0` to `delta_pct` over 800ms. Display as e.g., *"Retention +12.4%"*. | UX: count-up animation mandatory; 800ms duration | Counter animates; timing ~800ms |
| `[ ]` | **3.7.7** On new simulate result, replace (not append) the previous `<ResultBadge>`. | F-04 FR-04-20 | Second simulate → first badge replaced |
| `[ ]` | **3.7.8** On `/simulate` error: set `simulateError` in Zustand. Display error below `<SimulateButton>`. | API Layer: all errors produce visible UI state | Error message appears below button |

---

## 3.8 — Polish, Accessibility & Performance

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.8.1** Audit all interactive elements for unique `id` attributes: `id="chat-input"`, `id="simulate-button"`, `id="variable-select"`, `id="delta-slider"`, `id="upload-zone"`. | Component Design: unique IDs mandatory | All 5 IDs present in rendered HTML |
| `[ ]` | **3.8.2** Confirm `strict: true` in `tsconfig.json`. Run `npx tsc --noEmit` with zero errors. | TypeScript: strict mode; no `any` | TypeScript compiles with 0 errors |
| `[ ]` | **3.8.3** Run Lighthouse on the landing page (`/`). Achieve Performance ≥ 80. Fix any LCP or layout-shift issues (optimise font loading, lazy-load below-fold images). | F-04 NFR-04-04 | Lighthouse Performance ≥80 |
| `[ ]` | **3.8.4** Run Lighthouse on the app page (`/app`). Achieve Performance ≥ 75 (lower threshold due to chart animations). | F-04 NFR-04-04 | Lighthouse Performance ≥75 |
| `[ ]` | **3.8.5** Time the full demo flow with a stopwatch: upload → ask → see insight → simulate. Target ≤ 60 seconds end-to-end. | PRD §3 Success Criteria: ≤60s | Stopwatch confirms ≤60s |

---

## 3.9 — Vercel Deployment

| # | Task | Rule | Acceptance |
|---|---|---|---|
| `[ ]` | **3.9.1** Connect the GitHub repository to a new Vercel project via the Vercel dashboard (no CLI). Set Root Directory to `frontend/`. | Git & Deployment: no Vercel CLI | Vercel dashboard shows project |
| `[ ]` | **3.9.2** Set `NEXT_PUBLIC_BACKEND_URL` in Vercel project settings to the live Render.com backend URL. | Git & Deployment; API Layer: env var required | Environment variable saved in Vercel |
| `[ ]` | **3.9.3** Push to `main` and verify automatic Vercel deploy succeeds. | Git & Deployment: git push only | Vercel deployment log shows success |
| `[ ]` | **3.9.4** Lock CORS on the backend: update Render env var `CORS_ORIGIN` to the exact Vercel deployment URL. Restart Render service. | Security: CORS locked before demo | `/analyze` from Vercel URL succeeds; `/analyze` from random origin fails |
| `[ ]` | **3.9.5** Run the full end-to-end demo on the live Vercel + Render setup. Upload demo dataset → ask a question → read insight → simulate → confirm result badge animates. | Full system integration | No errors; demo flow completes in ≤60s |

---

---

# Phase 4 — Pre-Demo Checklist

> **Not a build phase — a verification gate before the demo moment.**

| # | Task | Check |
|---|---|---|
| `[ ]` | **4.1** Pre-warm Render backend by hitting `GET /health` at least 5 minutes before demo. Confirm 200 response and sub-200ms latency. | Render cold start mitigated |
| `[ ]` | **4.2** Open the live Vercel landing page in a fresh browser (incognito). Confirm all sections render, no broken images, "Launch to App" button works. | Landing page production-ready |
| `[ ]` | **4.3** Upload demo dataset. Confirm Header badge shows correct dataset name and row count. | F-01 live |
| `[ ]` | **4.4** Submit a prepared demo query. Confirm insight panel loads in < 2s. Confirm progressive reveal: Summary → Chart → Recommendation. | F-02 live; <2s metric met |
| `[ ]` | **4.5** Confirm `<RecommendationCard>` is visible without scrolling. No statistical jargon in the default view. | UX rules |
| `[ ]` | **4.6** Open `<ModelInfoCollapse>`. Confirm `decision_trace.reason` explains the engine choice in plain English. | Statistical Engine: trace always populated |
| `[ ]` | **4.7** Select a variable in `<SimulationBar>`, move slider to +20%, click Simulate. Confirm `<ResultBadge>` animates count-up and displays the impact percentage. | F-03 live; UX: count-up animation |
| `[ ]` | **4.8** Simulate again with a different variable. Confirm the previous badge is replaced, not appended. | F-04 FR-04-20 |
| `[ ]` | **4.9** Rotate through all 4 OpenAI API keys one by one. Confirm each key returns a valid response. | AI/LLM: key rotation verified before demo |
| `[ ]` | **4.10** Prepare the fallback plan: if OpenAI is unreachable, toggle `DEMO_FALLBACK_MODE=true` on Render to serve pre-computed cached insight for the demo dataset. | Error Handling: offline fallback |

---

## Estimated Build Timeline

| Phase | Estimated Hours | Key Risk |
|---|---|---|
| Phase 1 — Backend Core | 8–10h | PLS engine stability; bootstrap performance on Render |
| Phase 2 — AI / LLM Integration | 4–5h | Prompt token budget; LLM latency on free tier |
| Phase 3 — Frontend | 8–10h | Animation timing; CORS lockdown; Vercel env var setup |
| Phase 4 — Pre-Demo | 1–2h | Render cold-start; API key rotation |
| **Total** | **21–27h** | Within 20–30h PRD constraint |
