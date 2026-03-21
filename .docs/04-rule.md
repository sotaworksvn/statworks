# SOTA StatWorks — Development Rules

| Field            | Value                               |
|------------------|-------------------------------------|
| **Project**      | SOTA StatWorks                      |
| **Team**         | Phú Nhuận Builder x SOTA Works      |
| **Created**      | 2026-03-20                          |
| **Last updated** | 2026-03-21                          |
| **Source docs**  | `.docs/01-prd.md` · `.docs/02-system-design.md` · `.docs/03-features-spec.md` |

---

## Rule Index

| Domain | File | Rules |
|---|---|---|
| [Common — API Design](#common--api-design) | Applies to backend | Endpoint surface, response shape, error codes |
| [Common — Error Handling & Resilience](#common--error-handling--resilience) | Applies everywhere | Fallback chain, never crash policy |
| [Common — Security](#common--security) | Applies everywhere | API keys, CORS, input validation |
| [Common — Performance](#common--performance) | Applies to backend | Latency budgets, hard limits |
| [Common — Git & Deployment](#common--git--deployment) | Applies everywhere | Branch, deploy, env vars |
| [Python — General](#python--general) | FastAPI backend | Code style, type hints, imports |
| [Python — FastAPI](#python--fastapi) | FastAPI backend | Routing, Pydantic, async |
| [Python — Statistical Engine](#python--statistical-engine) | Math core | OLS, PLS, bootstrap rules |
| [Python — AI / LLM Layer](#python--ai--llm-layer) | OpenAI integration | Model usage, prompt design, cost control |
| [Python — Data Ingestion](#python--data-ingestion) | File parsing | Upload, store, parse rules |
| [TypeScript — General](#typescript--general) | Next.js frontend | Types, imports, naming |
| [React / Next.js — Component Design](#react--nextjs--component-design) | Frontend | Component rules, props, state |
| [React / Next.js — State Management](#react--nextjs--state-management) | Frontend | Zustand + React Query rules |
| [React / Next.js — API Layer](#react--nextjs--api-layer) | Frontend | Backend communication rules |
| [React / Next.js — UX & Animation](#react--nextjs--ux--animation) | Frontend | Insight rendering, animation, jargon |
| [Common — Authentication (Clerk)](#common--authentication-clerk) | Applies everywhere | Clerk integration, JWT, header rules |
| [Common — Storage (Cloudflare R2)](#common--storage-cloudflare-r2) | Backend + Frontend | Presigned URLs, bucket access, SDK |
| [Common — Metadata (Supabase)](#common--metadata-supabase) | Backend | Supabase client, tables, async writes |

---

---

## Common — API Design

**Source:** System Design §4, Feature Specs F-01/F-02/F-03

---

### Rule: All endpoints under `/api/*` prefix, grouped by page/feature

**What:** All backend endpoints MUST use the `/api/*` prefix and be grouped by page/feature using FastAPI `APIRouter` with prefixes:
- `/api/upload` — Upload: `POST /api/upload`, `POST /api/upload/presign`
- `/api/chat` — AI Chat: `POST /api/chat/analyze`, `GET/POST /api/chat/conversations`
- `/api/data` — Data Viewer: `GET /api/data/{id}/content`, `PATCH /api/data/{id}/cells`
- `/api/monitor` — Monitor: `POST /api/monitor/simulate`
- `/api/history` — History: `GET/POST /api/history`, `GET /api/history/{id}`, `GET /api/history/export-pdf`
- `/api/auth` — Authentication: `POST /api/auth/sync-user`
- `/api/health` — Health check: `GET /api/health`

Do not add new computation endpoints without explicit scope change in the PRD.

**Why:** Minimal surface area reduces demo failure risk within the 20–30h build window. Every new endpoint needs error handling, documentation, and testing.

---

### Rule: Always return a response body with application/json

**What:** Every endpoint MUST return `Content-Type: application/json` and a JSON body — including all error responses (4xx, 5xx). Never return an empty body.

**Why:** The frontend always deserialises the response and reads `detail` or `error` from it. Empty or non-JSON bodies crash the client error handler.

**Example:**
```python
# ✅ Correct
raise HTTPException(status_code=404, detail="file_id not found. Please upload a dataset first.")

# ❌ Wrong
return Response(status_code=404)  # no body
```

---

### Rule: Standardised response shape for all success responses

**What:** All success responses from `/analyze` MUST include `summary`, `drivers`, `r2`, `recommendation`, `model_type`, and `decision_trace`. All success responses from `/simulate` MUST include `variable`, `delta`, and `impacts`. Never add or remove top-level keys without updating the feature spec.

**Why:** The frontend deserialises by key name — unexpected or missing keys cause silent rendering bugs.

---

### Rule: Use HTTP status codes exactly as specified

**What:** Follow the status code contract defined in the feature spec:
- `200` — success
- `404` — unknown `file_id`
- `409` — `/simulate` called before `/analyze`
- `413` — file exceeds 10 MB
- `415` — unsupported file extension
- `422` — request schema violation (Pydantic) or business rule violation (e.g. multiple primary files)

Do not use `400` as a catch-all. Each error case has a distinct code.

**Why:** The frontend and any integration tests map status codes to specific UI states. A wrong code routes the error to the wrong handler.

---

### Rule: Include a `GET /health` endpoint

**What:** Implement `GET /health` returning `{ "status": "ok" }` with HTTP 200. This endpoint requires no authentication and no logic.

**Why:** Render.com free tier spins down after 15 minutes. The health endpoint is used to pre-warm the server before a demo and by external uptime monitors (e.g. UptimeRobot).

---

---

## Common — Error Handling & Resilience

**Source:** System Design §6.4, Feature Spec F-02 §4 Failure Flows

---

### Rule: The 4-layer fallback chain is non-negotiable

**What:** The `/analyze` pipeline MUST implement all four fallback layers in order. Never remove a layer or short-circuit to a hard crash:

1. **LLM Call 1 fails** → auto-select all numeric columns as features; infer target from column name heuristics.
2. **PLS engine fails** → fall back to OLS regression; update `decision_trace.reason`.
3. **OLS engine fails** → return a valid JSON response with `drivers: []`, `r2: null`, and a human-readable `recommendation` message.
4. **LLM Call 2 fails** → use the template string: `"{top_driver} shows the strongest relationship with {target} (β={coef:.2f})."` as `summary`; skip narrative `recommendation`.

**Why:** The system must return a valid response 100% of the time (NFR-02-06). A crash or empty response during a live demo is an unrecoverable failure.

---

### Rule: Never let an unhandled exception reach the client as a 500

**What:** Wrap the entire `/analyze` and `/simulate` handler bodies in a top-level `try/except`. Catch all unexpected exceptions, log them server-side, and return a structured `{ "detail": "Unexpected error. Please try again." }` with HTTP 500.

**Why:** Unhandled exceptions return FastAPI default error objects which are not consistent with the standard error shape the frontend expects.

---

### Rule: LLM retry before fallback — exactly ×2

**What:** Any LLM call MUST be retried exactly twice (total 3 attempts) with a 500ms sleep between attempts before triggering the next fallback layer. Do not retry more than twice — it blows the < 2s latency budget.

```python
for attempt in range(3):
    try:
        result = call_llm(...)
        break
    except Exception:
        if attempt == 2:
            trigger_fallback()
        else:
            await asyncio.sleep(0.5)
```

**Why:** Free-tier API calls occasionally time out once. A single retry recovers most transient failures. More retries exceed the 2s response target.

---

### Rule: DFS cycle detection is mandatory in the simulation engine

**What:** The simulation graph traversal MUST maintain a `visited: set` and skip any node already in the set during DFS. Do not skip this check even if you believe the current dataset cannot produce cycles.

**Why:** User-uploaded datasets may have circular correlations that produce a cyclic coefficient graph. Without cycle detection the DFS will recurse infinitely.

---

---

## Common — Security

**Source:** System Design §6.1

---

### Rule: All API keys and service credentials go in environment variables — never in source code

**What:** The following credentials MUST be read from environment variables at runtime. Never hardcode any of these in Python files, `.env` files committed to git, or frontend code:
- OpenAI: `OPENAI_API_KEY_1` through `OPENAI_API_KEY_4`
- Clerk: `CLERK_SECRET_KEY` (backend), `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (frontend)
- Supabase: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- R2: `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`

**Why:** Committing secrets to git exposes them permanently, even after deletion. Render.com and Vercel both support environment variable injection at the platform level.

---

### Rule: CORS must be locked to the Vercel frontend origin before demo

**What:** During development, CORS may be set to `allow_origins=["*"]`. Before the demo, `allow_origins` MUST be updated to the exact Vercel deployment URL. This is a required pre-demo checklist item.

```python
# ✅ Production / demo
app.add_middleware(CORSMiddleware, allow_origins=["https://sota-statworks.vercel.app"])

# ❌ Never in demo/production
app.add_middleware(CORSMiddleware, allow_origins=["*"])
```

**Why:** An open CORS policy on a public URL allows any origin to call the API and consume the sponsored API credit.

---

### Rule: Validate all file uploads before parsing

**What:** Before calling any parser (`pandas.read_excel`, `python-docx`, etc.), enforce:
1. File size ≤ 10 MB — return HTTP 413 immediately if exceeded
2. File extension in allowlist `{.xlsx, .csv, .docx, .pptx}` — return HTTP 415 for any other extension
3. Exactly one primary file (`.xlsx` or `.csv`) per request — return HTTP 422 if multiple

**Why:** Skipping pre-validation allows malformed or oversized files to crash the pandas parser, which can exhaust Render's 512 MB RAM.

---

### Rule: LLM output MUST pass through the Validation Layer before reaching any computation

**What:** Never pass a raw LLM string or parsed dict directly to the statistical engine. Always run it through `validate_parsed_intent(parsed, df_columns)` which strips unknown column names, infers missing target, and applies fallback feature selection.

**Why:** If the LLM hallucinates a column name that does not exist in the DataFrame, the regression engine will crash with a `KeyError`. The Validation Layer is the only guard between LLM output and `numpy`.

---

---

## Common — Performance

**Source:** PRD §3 Success Criteria, System Design §6.3, Feature Spec F-02 NFR

---

### Rule: `/analyze` MUST complete in under 2 seconds — enforce at the handler level

**What:** The `/analyze` handler should measure wall-clock time. If a full run is approaching 1.8s during development, investigate first (bootstrap count? LLM latency?) before committing. Do not add any synchronous I/O, subprocess calls, or blocking sleeps inside the handler without timing them.

**Why:** The < 2s target is a hard PRD success criterion measured during the demo. Latency creep is invisible until it fails publicly.

---

### Rule: Bootstrap sample count is capped at 200

**What:** The `n_bootstrap` parameter in both the regression and PLS engines MUST default to `200` and MUST NOT exceed `200` in v1 without explicit approval. Do not increase it to improve statistical accuracy — accuracy is sufficient for demo.

**Why:** Bootstrap at 200 iterations is the primary latency contributor in the statistical computation. At 500+ samples, the 2s budget is at risk on Render's free tier CPUs.

---

### Rule: LLM token budget per call is capped at 1000

**What:** The combined length of system prompt + user prompt for any single LLM call MUST stay under 1000 tokens. Measure this during prompt development. Trim column lists, truncate context text, or shorten system prompts if the budget is exceeded.

**Why:** Larger prompts increase both latency and cost. At 1000 tokens, LLM call cost is ~$0.00075 (Call 1) + ~$0.0025 (Call 2) = ~$0.003 total per request, safely within the $400 budget.

---

### Rule: The in-memory store is capped at 10 entries (LRU eviction)

**What:** The `file_store: OrderedDict` MUST evict the oldest entry when it reaches 10 items. Implement this in the store's write method, not ad-hoc at the call site.

```python
if len(file_store) >= 10:
    file_store.popitem(last=False)  # remove oldest
file_store[file_id] = entry
```

**Why:** Render's free tier has 512 MB RAM. Without eviction, repeated uploads during testing accumulate DataFrames and eventually crash the process.

---

### Rule: `/simulate` must not re-run the statistical model

**What:** `POST /simulate` MUST read only the `coefficient_cache` stored by `/analyze`. It MUST NOT call any statistical engine function or any LLM. Any proposal to add computation to `/simulate` is a scope violation.

**Why:** `/simulate` has a < 1s latency target. DFS on a small graph is O(n). Re-running OLS or making an LLM call would push the response to 2–3s.

---

---

## Common — Git & Deployment

**Source:** System Design §3, §8

---

### Rule: Frontend deploys via `git push main` — never via Vercel CLI

**What:** All frontend deployments happen by pushing to the `main` branch. The Vercel project is connected to the GitHub repository via the Vercel dashboard (one-time setup). Do not install or use `vercel` CLI in the project.

**Why:** PRD constraint. The Vercel CLI adds an additional setup step that can fail under hackathon time pressure and introduces environment inconsistencies.

---

### Rule: Backend environment variables are set in Render's dashboard — never in `.env` files committed to git

**What:** All backend secrets (`OPENAI_API_KEY_*`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `R2_*`, `CLERK_SECRET_KEY`) and config (`CORS_ORIGIN`) are injected via the Render.com environment variable panel. A `.env` file may exist locally for development but MUST be in `.gitignore`.

**Why:** Committed `.env` files expose secrets in git history and defeat the purpose of secret management.

---

### Rule: `NEXT_PUBLIC_BACKEND_URL` must be set in Vercel project settings before first deploy

**What:** The Next.js frontend reads the backend URL exclusively from `process.env.NEXT_PUBLIC_BACKEND_URL`. This variable MUST be set in the Vercel project's environment variable panel before the first deploy. Hard-coded URLs in `lib/api.ts` are forbidden.

**Why:** A hardcoded Render URL will break if the backend service is recreated, and it cannot be changed without a code push.

---

### Rule: Never commit node_modules, __pycache__, or .env to git

**What:** The `.gitignore` MUST include at minimum: `node_modules/`, `__pycache__/`, `*.pyc`, `.env`, `.env.local`, `.next/`, `dist/`.

**Why:** Committing these directories bloats the repository, breaks deployments, and in the case of `.env`, exposes secrets.

---

---

## Python — General

**Source:** System Design §3 Tech Stack

---

### Rule: Python version is 3.11+

**What:** All backend code MUST be written for Python 3.11 or later. Use `python_requires = ">=3.11"` in `pyproject.toml`. Do not use syntax or stdlib features that require Python 3.12+ unless confirmed available on Render.

**Why:** Render.com's Python Web Service defaults to 3.11. Targeting 3.12+ without confirming Render support causes runtime failures on deploy.

---

### Rule: All function signatures MUST have type hints

**What:** Every function and method in the backend MUST have fully annotated parameters and return types. Use `from __future__ import annotations` at the top of files with forward references.

```python
# ✅ Correct
def compute_ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    ...

# ❌ Wrong
def compute_ols(X, y):
    ...
```

**Why:** FastAPI's Pydantic integration relies on type hints for automatic validation. Missing hints produce silent validation gaps and obscure bugs.

---

### Rule: Use `numpy.linalg.lstsq` for OLS — never explicit matrix inversion

**What:** OLS coefficients MUST be computed via `np.linalg.lstsq(X, y, rcond=None)`. Do not use `np.linalg.inv(X.T @ X) @ X.T @ y`.

**Why:** `lstsq` uses LAPACK routines that are numerically stable for near-singular matrices. Explicit inversion raises `LinAlgError` on rank-deficient data, which is common in real-world datasets.

---

---

## Python — FastAPI

**Source:** System Design §4.4, Feature Specs §2 FRs

---

### Rule: All request bodies must be Pydantic models

**What:** Every endpoint that accepts a JSON body MUST define a `pydantic.BaseModel` for that body. Never use `request: Request` with manual `await request.json()`.

```python
# ✅ Correct
class AnalyzeRequest(BaseModel):
    file_id: str
    query: str

@app.post("/analyze")
async def analyze(body: AnalyzeRequest): ...

# ❌ Wrong
@app.post("/analyze")
async def analyze(request: Request):
    data = await request.json()
```

**Why:** Pydantic provides automatic type coercion, validation, and structured 422 error responses. Manual JSON parsing bypasses all of this.

---

### Rule: All endpoints must be `async def`

**What:** Every FastAPI route handler MUST be declared with `async def`. Synchronous `def` endpoints block the event loop.

**Why:** FastAPI runs on an async event loop (Uvicorn). Synchronous handlers prevent other requests from being processed during blocking operations (e.g. file parsing, LLM calls with `httpx`).

---

### Rule: Use `asyncio.Lock` to protect the in-memory store

**What:** All read and write operations on `file_store` MUST be wrapped with `async with store_lock:`. The lock MUST be a module-level `asyncio.Lock()` instance.

**Why:** Python's `dict` is not thread-safe for concurrent async writes. Without the lock, concurrent upload requests can corrupt the store under multi-connection Uvicorn.

---

### Rule: Use the `openai` Python SDK — not raw `requests`

**What:** All calls to OpenAI API MUST use the `openai` Python SDK (`from openai import AsyncOpenAI`). Never use `requests.post` or `httpx.post` directly against the OpenAI API.

**Why:** The official SDK handles retries, timeout configuration, JSON mode, function calling serialisation, and rate-limit backoff natively. Raw HTTP calls require reimplementing all of this.

---

---

## Python — Statistical Engine

**Source:** System Design §4.4, Feature Spec F-02 §6 Technical Decisions

---

### Rule: OLS uses `gpt-5.4-mini` validates features — engine never receives un-validated columns

**What:** The regression and PLS engines MUST only be called after the Validation Layer has cleaned the feature list. The engine functions MUST accept only column names guaranteed to exist in the DataFrame. Never pass the raw LLM `features[]` directly to an engine.

**Why:** A `KeyError` inside `numpy` matrix construction is uncaught by the engine and propagates as a 500. The Validation Layer is the single gatekeeper.

---

### Rule: PLS latent variable is computed as the mean of indicator columns

**What:** In v1, the PLS latent variable score is `LV = df[indicator_columns].mean(axis=1)`. Do not implement NIPALS, SIMPLS, or any iterative PLS algorithm.

**Why:** Full PLS iterative algorithms exceed the 20–30h build window and offer no meaningful accuracy improvement on demo-scale datasets. The simplified mean-based LV is statistically defensible for the use case.

---

### Rule: Bootstrap uses a fixed random seed for reproducibility

**What:** All bootstrap sampling MUST use `np.random.default_rng(seed=42)`. The seed MUST be hardcoded for v1. Do not use `np.random.seed()` (global state mutation).

```python
rng = np.random.default_rng(seed=42)
bootstrap_indices = rng.choice(n, size=(n_bootstrap, n), replace=True)
```

**Why:** Reproducible results allow the team to validate outputs against known demo datasets before presenting. Non-reproducible bootstrap p-values change on every run and cannot be pre-verified.

---

### Rule: The `decision_trace` object is always populated and returned

**What:** Every call to `/analyze` MUST return a `decision_trace` object containing at minimum: `score_pls`, `score_reg`, `engine_selected`, and `reason`. Even when a fallback occurs, the trace must reflect the actual engine used and state the fallback reason.

**Why:** `decision_trace` is both a debugging tool during development and a transparency feature for judges. An empty or missing trace removes the AI decision-making narrative from the demo.

---

---

## Python — AI / LLM Layer

**Source:** System Design §3/§5/§8, Feature Spec F-02 §2/§6

---

### Rule: `gpt-5.4-mini` is the ONLY model for LLM Call 1 (intent parsing)

**What:** LLM Call 1 (intent classification and variable extraction) MUST use model `"gpt-5.4-mini"` with `response_format={"type": "json_object"}`. Do not use `gpt-5.4` for Call 1 — it is over-qualified and more expensive for a structured extraction task.

**Why:** `gpt-5.4-mini` has a 400K context window, native JSON mode, function calling support, and runs 2× faster than the flagship model. These properties match the < 2s latency requirement exactly.

---

### Rule: `gpt-5.4` is the ONLY model for LLM Call 2 (insight generation)

**What:** LLM Call 2 (business-language summary and recommendation) MUST use model `"gpt-5.4"`. Do not substitute a cheaper model for Call 2 — the prose quality of the recommendation is a primary demo differentiator.

**Why:** `gpt-5.4` is OpenAI's current frontier model (released March 5, 2026), with 33% fewer factual errors vs GPT-5.2. The recommendation text is literally what judges read and evaluate. The cost difference (~$0.0025/call) is negligible against $400 budget.

---

### Rule: Maximum 2 LLM calls per `/analyze` request

**What:** The `/analyze` handler MUST issue exactly 2 LLM calls in the happy path: one for parsing, one for insight. No chain-of-thought, no intermediate classification, no additional context calls. If either call fails and the fallback is triggered, the fallback does NOT make an additional LLM call.

**Why:** Two calls at ≤1k tokens each is the budget ceiling that keeps total request latency under 2s. Each additional call adds ~300–500ms.

---

### Rule: System prompt for Call 1 must enforce strict JSON schema

**What:** The Call 1 system prompt MUST contain the exact expected JSON schema and instruction `"Return ONLY valid JSON matching the schema below. Do not include markdown, code fences, or explanation."` The schema in the prompt must match the Pydantic model used for parsing.

```python
SYSTEM_PROMPT_PARSE = """
You are a data analysis assistant.
Return ONLY valid JSON matching this schema:
{"intent": "driver_analysis|summary|comparison", "target": "string", "features": ["string"]}
Rules:
- Use only column names from the dataset.
- Do not hallucinate column names.
- If unsure about features, return an empty list.
"""
```

**Why:** `gpt-5.4-mini` with JSON mode enabled still benefits from schema hints in the prompt to produce the correct key names. Without explicit schema, key naming varies and breaks downstream Pydantic validation.

---

### Rule: The API key rotation order is fixed and documented

**What:** The backend MUST attempt OpenAI API calls in this priority order: `OPENAI_API_KEY_1` → `OPENAI_API_KEY_2` → `OPENAI_API_KEY_3` → `OPENAI_API_KEY_4`. Key rotation happens only on `RateLimitError`, not on other errors. Document the key assignment (which team member owns which key) in the README, never in code.

**Why:** Predictable key rotation order prevents all four keys being exercised simultaneously under load, which would trigger rate limits on all accounts at once.

---

---

## Python — Data Ingestion

**Source:** Feature Spec F-01

---

### Rule: One primary data file per request — enforce before parsing

**What:** Count `.xlsx` and `.csv` files in the upload before calling any parser. If count > 1, return HTTP 422 immediately. The check MUST happen at the routing layer, not inside the parser function.

**Why:** Calling `pandas.read_excel` on two files without knowing which is primary causes ambiguous column merging. Detecting this before parsing prevents wasteful computation on an invalid request.

---

### Rule: Context text from `.docx` / `.pptx` is plain text only

**What:** When parsing `.docx`, extract only `paragraph.text` for each paragraph. When parsing `.pptx`, extract only the `.text` from each `shape.text_frame`. Never extract images, tables, charts, or formatting. Concatenate all extracted strings with `"\n"` separator.

**Why:** The extracted text is appended to LLM prompts. Binary content or rich formatting balloons token count beyond the 1000-token budget.

---

### Rule: DataFrame column names are stripped but NOT lowercased

**What:** After parsing, apply `df.columns = df.columns.str.strip()` to remove leading/trailing whitespace. Do not lowercase column names. Preserve original casing for LLM variable matching.

**Why:** Lowercasing breaks the LLM's ability to match user-written column names (e.g., user types "Retention" but the column is stored as "retention" → mismatch in the Validation Layer).

---

---

## TypeScript — General

**Source:** System Design §3 Tech Stack, Feature Spec F-04

---

### Rule: `strict` mode is always enabled in `tsconfig.json`

**What:** `tsconfig.json` MUST include `"strict": true`. Never disable individual strict checks (`noImplicitAny`, `strictNullChecks`, etc.) to silence an error — fix the type instead.

**Why:** Strict TypeScript is the primary defence against runtime `undefined is not a function` errors in the frontend. The demo has no time to debug type errors at runtime.

---

### Rule: No `any` type — use `unknown` and narrow

**What:** `any` is forbidden in all frontend code. Use `unknown` for untyped external data (e.g. API responses before validation), then narrow with type guards or `zod` parsing.

**Why:** `any` defeats TypeScript's type system entirely. Errors that `any` masks will appear as runtime crashes during the demo.

---

### Rule: All API response types must be explicitly typed

**What:** Define TypeScript interfaces (`InsightResult`, `SimulationResult`, `UploadResult`) for every API response shape. Never destructure an API response without first asserting it against its interface.

```typescript
// ✅ Correct
const data: InsightResult = await res.json()
const { summary, drivers } = data

// ❌ Wrong
const data = await res.json()
const { summary, drivers } = data  // data is `any`
```

**Why:** Typed API responses enable IDE autocomplete, catch breaking backend contract changes at compile time, and prevent silent `undefined` rendering in components.

---

---

## React / Next.js — Component Design

**Source:** System Design §4.5, Feature Spec F-04 §2/§4

---

### Rule: Sidebar navigation with five views + URL routing — see ADR-0004, ADR-0005

**What:** The application uses a Canva-inspired vertical sidebar navigation with five main views: Upload, AI Chat, Data Viewer, Monitor, and History. The sidebar has a light white-to-blue gradient background with a shadow divider. Logo toggles between `icon.png` (collapsed) and `logo.png` (expanded). Views are routed via a Next.js catch-all route `app/app/[[...slug]]/page.tsx` that syncs URL ↔ Zustand `activeView`. The sidebar uses `router.push` to update the browser address bar. Routes: `/app` (Upload), `/app/chat`, `/app/viewer`, `/app/monitor`, `/app/monitor/data-analysis`, `/app/monitor/impact-analysis`, `/app/history/chat`, `/app/history/viewer`, `/app/history/monitor`.

**Why:** The product has expanded to include Data Viewer, Monitor (Data Analysis + Impact Analysis), and Chat History, which each need full-screen space. A sidebar provides persistent navigation context. URL routing enables browser back/forward and bookmark support. See ADR-0004 for navigation rationale, ADR-0005 for chat history persistence.

---

### Rule: Components never fetch data directly — use `lib/api.ts`

**What:** No component may call `fetch()` directly. All API calls MUST go through the typed functions in `lib/api.ts` (`analyzeDataset`, `simulateScenario`, `uploadFile`). Components call these functions via React Query mutations or Zustand actions.

**Why:** Centralising API calls in `lib/api.ts` ensures that `NEXT_PUBLIC_BACKEND_URL` is resolved in one place, error handling is consistent, and response typing is enforced.

---

### Rule: The `<RecommendationCard>` must always be visible without scrolling

**What:** The CSS layout MUST ensure that `<RecommendationCard>` is visible in the viewport on a 1280px+ screen without vertical scrolling. If the insight panel overflows, reduce font sizes or truncate the driver list — never push the recommendation below the fold.

**Why:** The recommendation is the product's core promise. If a judge has to scroll to find it, the demo fails the "10-second comprehension" standard defined in the PRD.

---

### Rule: All interactive elements must have unique `id` attributes

**What:** Every interactive HTML element (button, input, slider, dropdown) MUST have a unique, descriptive `id`. Prefer `id="chat-input"`, `id="simulate-button"`, `id="variable-select"`, `id="delta-slider"` as defined in Feature Spec F-04.

**Why:** Unique IDs are required for browser testing tools and accessibility. They also enable E2E test selectors that don't break when class names change.

---

---

## React / Next.js — State Management

**Source:** System Design §3, Feature Spec F-04 §3

---

### Rule: Global UI state lives in Zustand — server state lives in React Query

**What:**
- `fileId`, `datasetName`, `rowCount`, `columns`, `insight`, `simulation`, `isAnalyzing`, `isSimulating`, `analyzeError`, `simulateError` → **Zustand store** (`lib/store.ts`)
- API fetching, caching, loading/error lifecycle for `/analyze` and `/simulate` → **React Query mutations**

Never put server data (API responses) into Zustand. Never put local UI state into React Query.

**Why:** Mixing state layers causes stale-fetch bugs and cache invalidation issues. The boundary is: if it came from the server, React Query owns it; if it's derived UI state, Zustand owns it.

---

### Rule: The Zustand store is the single source of truth for `fileId`

**What:** `fileId` is stored in Zustand immediately after a successful upload. Every subsequent API call (`/analyze`, `/simulate`) reads `fileId` from the Zustand store — never from component local state or a ref.

**Why:** If `fileId` lives in component state, it is lost when the component unmounts or re-mounts. The Zustand store survives component lifecycle changes within the session.

---

---

## React / Next.js — API Layer

**Source:** System Design §7 Constraints, Feature Spec F-04 §6 Technical Decisions

---

### Rule: Backend URL is always read from `NEXT_PUBLIC_BACKEND_URL`

**What:** `lib/api.ts` MUST read the backend base URL as:
```typescript
const BASE_URL = process.env.NEXT_PUBLIC_BACKEND_URL
if (!BASE_URL) throw new Error("NEXT_PUBLIC_BACKEND_URL is not set")
```
No fallback to `localhost` in non-development environments. Fail loudly if the variable is missing.

**Why:** A missing `NEXT_PUBLIC_BACKEND_URL` silently falls back to `localhost` and appears to work in dev but fails on Vercel. Failing loudly during build catches misconfiguration before deploy.

---

### Rule: All API errors must produce a visible UI error state — never a silent failure

**What:** Every React Query mutation MUST handle `onError` and update the corresponding Zustand error field (`analyzeError` or `simulateError`). The component MUST render a visible error message when the field is non-null. A blank panel with no feedback is not acceptable.

**Why:** Silent failures during a demo look like the app is broken. A visible error message (even "Something went wrong — please try again") is always preferable.

---

---

## React / Next.js — UX & Animation

**Source:** PRD §4, Feature Spec F-04 §2 FR

---

### Rule: InsightPanel reveals progressively in order — never all at once

**What:** After a successful `/analyze` response, the three Insight sub-components MUST animate in sequence:
1. `<SummaryCard>` (fade in, 0ms delay)
2. `<DriverChart>` (bars grow, 200ms delay)
3. `<RecommendationCard>` (fade in, 400ms delay)

Use Framer Motion `initial={{ opacity: 0 }}` + `animate={{ opacity: 1 }}` with `transition={{ delay }}`. Never render all three simultaneously.

**Why:** Progressive reveal creates the perception that the AI is "thinking and surfacing" conclusions, which is the core wow moment of the demo.

---

### Rule: Never display statistical jargon in the default view

**What:** The following terms MUST NOT appear in any visible UI text by default: `coefficient`, `p-value`, `β`, `R²`, `OLS`, `PLS`, `SEM`, `regression`, `bootstrap`, `latent variable`. These terms are only permitted inside the `<ModelInfoCollapse>` section, which is collapsed by default.

**Why:** The PRD defines the success criterion: *"if users see statistics, we failed; if they see decisions, we win."* Exposing jargon to a non-technical judge immediately signals a tool for statisticians, not for decision-makers.

---

### Rule: Simulation `<ResultBadge>` uses count-up animation

**What:** When a simulation result arrives, the displayed `delta_pct` value MUST animate from `0` to the target value using Framer Motion's `useSpring` or a count-up hook. The animation duration MUST be 800ms ± 200ms. Never render the final value instantly.

**Why:** The count-up is the single highest-impact animation in the demo. It creates the impression that the AI is computing in real time. An instant value update reads as a static label swap.

---

### Rule: Suggested prompts disappear after the first query is submitted

**What:** `<SuggestedPrompts>` MUST be hidden once the user has submitted at least one message (i.e., the message list is non-empty). They should not reappear unless the dataset is replaced.

**Why:** Persistent suggested prompts after a response has been shown create visual clutter and distract from the insight panel. They serve only as a cold-start affordance.

---

---

## Appendix — Rule Sources

| Rule Group | Source Document |
|---|---|
| API Design, Error Handling, Security, Performance | `.docs/02-system-design.md` §4, §6 |
| Git & Deployment | `.docs/02-system-design.md` §7, §8 |
| Python / FastAPI / Statistical Engine / AI Layer | `.docs/02-system-design.md` §3; `.docs/03-features-spec.md` F-02 |
| Python / Data Ingestion | `.docs/03-features-spec.md` F-01 |
| TypeScript / React / Next.js | `.docs/02-system-design.md` §3; `.docs/03-features-spec.md` F-04 |
| UX & Animation | `.docs/01-prd.md` §4; `.docs/03-features-spec.md` F-04 §2 |
| Authentication (Clerk) | `.docs/02-system-design.md` §6.1; `.docs/03-features-spec.md` F-05; ADR-0001 |
| Storage (R2) | `.docs/02-system-design.md` §6.2; `.docs/03-features-spec.md` F-05; ADR-0003 |
| Metadata (Supabase) | `.docs/02-system-design.md` §6.2; `.docs/03-features-spec.md` F-05; ADR-0002 |

---

---

## Common — Authentication (Clerk)

**Source:** System Design §6.1, Feature Spec F-05, ADR-0001

---

### Rule: Backend extracts `clerk_user_id` from request header — no Clerk SDK on backend

**What:** The backend MUST extract the user identity from the `x-clerk-user-id` request header using a thin helper function in `auth/context.py`. Do not install or import any Clerk SDK package in the backend. The Clerk SDK is frontend-only (`@clerk/nextjs`).

```python
# ✅ Correct
def get_current_user_id(request: Request) -> str | None:
    return request.headers.get("x-clerk-user-id")

# ❌ Wrong
from clerk_backend_api import Clerk  # do not use
```

**Why:** The backend does not need Clerk's SDK. Adding it introduces an unnecessary dependency, increases attack surface, and couples the backend to Clerk's versioning. Header extraction is sufficient for identity.

---

### Rule: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is the only Clerk key in frontend code

**What:** The frontend MUST only use `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` (prefixed with `pk_`). The `CLERK_SECRET_KEY` (prefixed with `sk_`) MUST NEVER appear in frontend code, client-side bundles, or any file under `frontend/`.

**Why:** Clerk's secret key has full account access. Exposing it in a client-side bundle compromises all user sessions.

---

### Rule: Auth is optional — the app must work without Clerk

**What:** If `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` is not set or Clerk is unreachable, the frontend MUST still render the app in anonymous mode (no login, no "Welcome" message). The backend MUST treat a missing `x-clerk-user-id` header as an anonymous request and proceed with in-memory-only mode.

**Why:** The demo must work even if Clerk is down. Auth adds persistence and personalisation, not core functionality.

---

---

## Common — Storage (Cloudflare R2)

**Source:** System Design §6.2, Feature Spec F-05, ADR-0003

---

### Rule: All R2 access uses presigned URLs — never direct bucket access

**What:** Every upload to and download from R2 MUST use a time-limited presigned URL generated by the backend via `boto3`. The R2 bucket MUST NOT have public access enabled. Frontend code MUST NOT contain R2 credentials.

```python
# ✅ Correct
def generate_presigned_upload_url(key: str, expires_in: int = 3600) -> str:
    return s3_client.generate_presigned_url(
        "put_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=expires_in
    )
```

**Why:** Public bucket access allows anyone to read or overwrite user data. Presigned URLs are time-limited, scoped to a specific key, and revoke automatically.

---

### Rule: R2 keys follow canonical path structure

**What:** All objects stored in R2 MUST follow this naming convention:
- Datasets: `users/{clerk_user_id}/datasets/{dataset_id}.csv`
- Outputs: `users/{clerk_user_id}/outputs/{analysis_id}.json`

Never store files at the bucket root or with flat naming.

**Why:** Structured paths enable per-user cleanup, debugging, and future RLS-style access control at the storage layer.

---

### Rule: Use `boto3` with S3-compatible endpoint — never Cloudflare-specific SDKs

**What:** The R2 client in `storage/r2.py` MUST use `boto3` configured with `endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"`. Do not use any Cloudflare-specific SDK.

**Why:** `boto3` is the standard S3 SDK. Using it ensures the storage layer can be migrated to AWS S3 or MinIO without code changes.

---

---

## Common — Metadata (Supabase)

**Source:** System Design §6.2, Feature Spec F-05, ADR-0002

---

### Rule: Supabase writes are async and non-blocking

**What:** All Supabase insert/update operations (user upsert, dataset metadata, analysis result) MUST be dispatched asynchronously. The main request handler MUST NOT `await` Supabase writes in the critical path of `/analyze`. Use `asyncio.create_task()` or fire-and-forget pattern.

**Why:** The < 2s latency budget for `/analyze` is already tight. Adding a synchronous 100–300ms Supabase roundtrip would push the total over budget.

---

### Rule: Use `supabase-py` client — never raw HTTP to the Supabase REST API

**What:** All Supabase interactions MUST use the `supabase-py` Python client. Do not use `requests` or `httpx` directly against the Supabase PostgREST API.

```python
# ✅ Correct
from supabase import create_client
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

# ❌ Wrong
requests.post(f"{SUPABASE_URL}/rest/v1/users", ...)
```

**Why:** The official client handles authentication headers, error formatting, and type serialisation. Raw HTTP calls bypass all of this.

---

### Rule: `SUPABASE_SERVICE_KEY` is backend-only — never in frontend code

**What:** The Supabase service key (`service_role` key) MUST only be used in the backend (`backend/db/supabase.py`). It MUST NEVER appear in frontend code, `NEXT_PUBLIC_*` env vars, or client-side bundles. The frontend communicates with Supabase only through the backend API.

**Why:** The service key bypasses Row Level Security. Exposing it in the frontend allows any user to read/write all data in all tables.

---

### Rule: Supabase is optional — fall back to in-memory if unreachable

**What:** If `SUPABASE_URL` or `SUPABASE_SERVICE_KEY` is not set, or if the Supabase client raises a connection error, the backend MUST fall back gracefully to in-memory-only mode. Log a warning but do not crash.

**Why:** Core statistical functionality must never depend on an external metadata store. Supabase adds persistence, not capability.
