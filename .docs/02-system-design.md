# SOTA StatWorks — System Design

| Field           | Value                               |
|-----------------|-------------------------------------|
| **Status**      | `draft`                             |
| **Team**        | Phú Nhuận Builder x SOTA Works      |
| **Project**     | SOTA StatWorks                      |
| **Created**     | 2026-03-20                          |
| **Last updated**| 2026-03-20                          |
| **PRD**         | `.docs/01-prd.md`                   |

---

## 1. Mission

SOTA StatWorks is an AI-powered decision engine that accepts raw tabular data and natural-language questions, runs statistical modeling (OLS regression or PLS-SEM), and returns ranked insight plus interactive scenario simulation — all without requiring the user to understand statistics.

It serves business analysts, product managers, marketers, and students who need decisions, not coefficient tables. It exists because no current tool bridges natural-language querying, real statistical computation, and what-if simulation in a single, accessible interface.

---

## 2. Design Principles

| Principle | Why it matters for this system |
|---|---|
| **Decisions over data** | Every API response must terminate in a human-readable recommendation. Returning raw numbers without interpretation is a failure mode. |
| **Stateless by default** | No database, no session store. Each request carries all needed context. Eliminates deployment complexity and lets the free Render.com tier handle the load. |
| **Fail gracefully, never crash** | Free-tier LLMs produce malformed output unpredictably. The system must always return a valid response — degraded if necessary — via a layered fallback chain. |
| **Latency budget is a hard constraint** | The PRD sets < 2s for `/analyze`. Every design decision (bootstrap cap, token cap, in-process computation) must be evaluated against this budget first. |
| **LLM is an orchestrator, not the brain** | LLM handles parsing and narrative. Statistical truth comes from deterministic code (`numpy`, `scipy`). This separation prevents hallucination from corrupting quantitative output. |
| **Minimal surface area** | Three endpoints, one screen. Each additional endpoint or page increases demo failure risk within the 20–30h build window. |

---

## 3. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **API framework** | FastAPI (Python 3.11+) | Async support; automatic OpenAPI docs useful for FE integration |
| **Statistical core** | `numpy`, `scipy`, `pandas` | OLS via `numpy` matrix ops; bootstrapping via `numpy.random`; PLS latent variable computation via `pandas` aggregation |
| **PLS extension** | `pyplspm` (optional) | Used only if custom PLS implementation proves unstable; adds dependency weight |
| **File parsing — Excel/CSV** | `pandas`, `openpyxl` | `pandas.read_excel` / `read_csv` as primary; `openpyxl` as engine |
| **File parsing — Word** | `python-docx` | Text extraction only; no formatting preserved |
| **File parsing — PowerPoint** | `python-pptx` | Text extraction from slide content; no media |
| **AI / LLM — Call 1 (parsing)** | OpenAI API · `gpt-5.4-mini` | Intent classification + variable extraction; JSON mode + function calling; 400K context window; $0.75/1M input, $4.50/1M output — ~$0.00075/request at ≤1k tokens |
| **AI / LLM — Call 2 (insight)** | OpenAI API · `gpt-5.4` | Business-language narrative generation; 272K standard context (1.05M extended); $2.50/1M input, $15.00/1M output — ~$0.0025/request; highest prose quality for judge impression |
| **Frontend framework** | Next.js 14 (App Router) + TypeScript | Deployed to Vercel via Git push (no Vercel CLI) |
| **Styling** | TailwindCSS | Utility-first; consistent with the single-screen layout constraint |
| **UI components** | Shadcn/UI | Accessible primitives; avoids building from scratch under time pressure |
| **Charts** | Recharts | Horizontal bar chart for driver ranking; lightweight, React-native |
| **Animation** | Framer Motion | Count-up numbers, fade-in panels, bar grow — core to the wow factor |
| **Client state** | Zustand | Minimal global store: `dataset`, `insight`, `simulation` |
| **Server state** | TanStack Query (React Query) | Handles loading / error / refetch lifecycle for `/analyze` and `/simulate` |
| **File upload (FE)** | `react-dropzone` | Drag-and-drop zone on the landing state |
| **Backend hosting** | Render.com (free tier) | Web Service; Python; cold-start latency ~30s (acceptable if pre-warmed before demo) |
| **Frontend hosting** | Vercel (hobby tier) | Deployed via GitHub push; no Vercel CLI required |
| **Async queue (optional)** | Celery + Redis | Only added if bootstrap > 200 samples is needed and blocks the 2s budget |

---

## 4. Architecture

### 4.1 High-Level Diagram

```mermaid
graph TD
    Browser["Browser\n(Next.js on Vercel)"]

    subgraph Render ["Render.com — FastAPI Backend"]
        API["API Gateway\nFastAPI router"]
        Ingest["Data Ingestion Layer\npandas · openpyxl · python-docx · python-pptx"]
        AILayer["AI Layer\nIntent Parser · Variable Extractor · Insight Generator"]
        Router["Decision Router\nScoring function: PLS vs Regression"]
        RegEngine["Regression Engine\nOLS · numpy · scipy"]
        PLSEngine["PLS Engine\nLatent vars · path coef · bootstrap"]
        SimEngine["Simulation Engine\nDirected graph · DFS propagation"]
    end

    OpenAI["OpenAI API\ngpt-5.4-mini (Call 1) · gpt-5.4 (Call 2)"]

    Browser -->|"POST /upload\nPOST /analyze\nPOST /simulate"| API
    API --> Ingest
    Ingest --> AILayer
    AILayer -->|"LLM call 1 — parse intent"| OpenAI
    OpenAI -->|"structured JSON"| AILayer
    AILayer --> Router
    Router --> RegEngine
    Router --> PLSEngine
    RegEngine --> SimEngine
    PLSEngine --> SimEngine
    SimEngine --> AILayer
    AILayer -->|"LLM call 2 — generate insight"| OpenAI
    OpenAI -->|"narrative text"| AILayer
    AILayer -->|"JSON response"| Browser
```

### 4.2 Request Lifecycle — `/analyze`

```
POST /analyze  { query: string, file_id: string }
│
├─ 1. Retrieve parsed dataset from in-memory store (file_id → DataFrame)
├─ 2. AI Layer — LLM call 1: intent + variable extraction
│      • system prompt: strict JSON schema
│      • user prompt: column names + query
│      → { intent, target, features }
│
├─ 3. Validation Layer
│      • strip features not in DataFrame columns
│      • auto-detect target if missing (last column / columns matching "index", "score")
│      • fallback: top N numeric columns as features
│
├─ 4. Decision Router
│      • compute score_pls = 0.4·L + 0.3·M + 0.3·C
│      • compute score_reg = 0.6·O + 0.4·(1−C)
│      • select engine
│
├─ 5. Statistical Engine (Regression or PLS)
│      • OLS: β = (XᵀX)⁻¹Xᵀy  →  R², p-values via bootstrap (≤200 samples)
│      • PLS: LV = mean(indicators) → path coef → bootstrap
│
├─ 6. AI Layer — LLM call 2: insight generation
│      • input: { drivers, r2, model_type }
│      • output: { summary, recommendation }
│
└─ 7. Return response
       { summary, drivers[{name, coef, p}], r2, recommendation, model_type }
```

### 4.3 Request Lifecycle — `/simulate`

```
POST /simulate  { variable: string, delta: float, file_id: string }
│
├─ 1. Load cached path coefficients from in-memory store
├─ 2. Build directed graph from coefficient map
│      graph = { "Trust": [("Retention", 0.62)], ... }
├─ 3. DFS propagation
│      ΔY = β · ΔX            (1-hop)
│      ΔZ = β_XZ·ΔX + β_YZ·(β_XY·ΔX)   (multi-hop)
└─ 4. Return { impacts: [{ variable, delta_pct }] }
```

### 4.4 Component Responsibilities

| Component | Owns | Exposes | Depends on |
|---|---|---|---|
| **API Gateway** | Routing, request validation (Pydantic), CORS | HTTP endpoints: `/upload`, `/analyze`, `/simulate` | All internal components |
| **Data Ingestion Layer** | File parsing, column type detection, in-memory DataFrame store | `DataFrame`, `file_id`, column metadata | `pandas`, `openpyxl`, `python-docx`, `python-pptx` |
| **AI Layer** | Prompt construction, LLM call management, retry logic, insight template | `ParsedIntent`, `InsightText` | OpenRouter API |
| **Validation Layer** | Schema enforcement on LLM output, fallback variable selection | Cleaned `ParsedIntent` | `DataFrame` column list |
| **Decision Router** | Model scoring, engine selection, decision trace logging | Engine choice (`regression` / `pls`) | None |
| **Regression Engine** | OLS computation, bootstrap, p-value estimation | `DriverResult[]`, `R²` | `numpy`, `scipy` |
| **PLS Engine** | Latent variable scoring, inner model path coefficients, bootstrap | `DriverResult[]`, `R²` | `numpy`, `pandas` |
| **Simulation Engine** | Graph construction, DFS impact propagation | `SimulationResult` | Coefficient map from stat engine |

### 4.5 Frontend Component Tree

```
<AppLayout>
  <Header>              — dataset name badge, upload button
  <Main>
    <ChatPanel>         — <MessageList> <SuggestedPrompts> <InputBox>
    <InsightPanel>      — <SummaryCard> <DriverChart> <RecommendationCard> <ModelInfoCollapse>
  <SimulationBar>       — <VariableSelect> <DeltaSlider> <SimulateButton> <ResultBadge>
```

---

## 5. External Dependencies

| Service | Purpose | Failure behavior |
|---|---|---|
| **OpenAI API (`gpt-5.4-mini`)** | LLM Call 1: intent classification and variable extraction (JSON mode + function calling); released March 17, 2026; 400K context window | Retry ×2 with 500ms backoff → if still failing, fallback: auto-detect features, template-generated summary string |
| **OpenAI API (`gpt-5.4`)** | LLM Call 2: business-language insight and recommendation generation; released March 5, 2026; up to 1.05M context; frontier reasoning model | Retry ×2 with 500ms backoff → if still failing, use template: `"{top_driver} shows the strongest relationship with {target} (β={coef:.2f})."` |
| **Render.com (free tier)** | Backend hosting | Cold start ~30s after inactivity; pre-warm by hitting `/health` before demo. Free tier has 512 MB RAM — keep DataFrame in-memory, not persisted |
| **Vercel (hobby tier)** | Frontend hosting | Deployed automatically on push to `main` branch; no CLI required. Serverless functions not used (all compute is on Render backend) |

---

## 6. Cross-Cutting Concerns

### 6.1 Security

**Assumptions:**
- No authentication layer. The system is stateless and demo-only; any user with the URL can upload data and query.
- Data uploaded to the backend is not persisted to disk. The parsed `DataFrame` is held in a Python process-level in-memory dict keyed by `file_id` (a UUID). It is lost on process restart.

**Known gaps:**
- No input size limit enforced at the HTTP layer (only application-level validation). A large file upload could exhaust Render's 512 MB RAM.
- `file_id` is not validated for ownership — any client knowing a `file_id` UUID can query against it. Acceptable for demo; not acceptable for production.
- OpenAI API keys (one per account, 4 accounts total) are stored as environment variables (`OPENAI_API_KEY_1` through `OPENAI_API_KEY_4`). Must not be committed to source control. Active key is rotated if rate-limited.

**Controls in place:**
- CORS restricted to the Vercel frontend origin (configured in FastAPI middleware).
- Pydantic models enforce request shape — malformed JSON is rejected at the boundary.
- LLM output is always passed through the Validation Layer before touching statistical computation; raw LLM text never reaches `numpy` directly.

### 6.2 Data Architecture

- **Primary storage:** In-process Python `dict` (`file_id → DataFrame`). No external store.
- **Lifecycle:** DataFrame is created on `POST /upload`, read on `POST /analyze` and `POST /simulate`. It expires when the Render process restarts (no TTL mechanism in v1).
- **Context files (`.docx`, `.pptx`):** Text is extracted at upload time and appended to the LLM prompt as plain string context. Not stored separately.
- **Coefficient cache:** After `/analyze`, the computed path coefficient map is stored alongside the DataFrame under the same `file_id`. This allows `/simulate` to skip re-running the statistical model.

### 6.3 Performance and Scalability

| Target | Mechanism |
|---|---|
| `/analyze` < 2s end-to-end | Bootstrap capped at 200 samples; LLM token budget ≤ 1k per call; in-process computation (no subprocess or queue overhead) |
| `/simulate` < 1s | Operates on cached coefficients; DFS on small graph (< 20 nodes); no LLM call |
| Render cold-start mitigation | Pre-warm by hitting `GET /health` before demo begins |
| Single concurrent user | Stateless design; in-memory dict is not thread-safe for concurrent writes. Acceptable for hackathon; production would need per-request state isolation |

**Hard limits (v1):**
- Maximum file size: 10 MB (enforced in `POST /upload`)
- Maximum bootstrap samples: 200
- Maximum LLM tokens per request: 1000 (system + user prompt combined)
- Maximum features surfaced in response: 5 (top N by absolute coefficient)

### 6.4 Error Handling and Resilience

The system uses a layered fallback chain, ensuring it never returns an empty response:

```
Layer 1 — LLM parse fails (malformed JSON or timeout)
  → Fallback: auto-select all numeric columns as features,
    detect target as last column or column matching "score"/"index"

Layer 2 — PLS engine fails (e.g. insufficient rows, singular matrix)
  → Fallback: always run OLS regression

Layer 3 — Regression engine fails (all-NaN column, zero variance)
  → Fallback: return { summary: "Insufficient data for analysis",
    drivers: [], r2: null, recommendation: "Please check your dataset." }

Layer 4 — LLM insight generation fails (Call 2)
  → Fallback: template-generated string:
    "{top_driver} shows the strongest relationship with {target} (β={coef:.2f})."
```

LLM calls use retry ×2 with 500ms backoff before triggering Layer 1 fallback.

---

## 7. Constraints

| Constraint | Architectural impact |
|---|---|
| **Backend on Render.com free tier** | 512 MB RAM ceiling → no large matrix ops; no persistent disk; cold-start requires pre-warming |
| **Frontend on Vercel, no CLI** | Deployment exclusively via `git push` to `main`; no server-side compute on Vercel; all API calls proxied to Render |
| **No database** | All state is ephemeral in-process; `file_id` is the only key; no user sessions |
| **Free LLM (OpenRouter)** | Rate limits apply; structured output is not guaranteed; validation layer and fallback chain are load-bearing |
| **≤ 2 LLM calls per `/analyze` request** | Prohibits chain-of-thought or multi-step reasoning via LLM; all branching logic must live in deterministic Python code |
| **< 2s response for `/analyze`** | Bootstrap ≤ 200 samples; no async queue for v1; no heavy pre-processing |
| **20–30h build window** | Scope is fixed; optional features (Celery, full PLS, PDF export) are not built unless core is complete and time remains |

---

## 8. Architecture Rationale

**Why FastAPI over Flask or Django?**
FastAPI's async support, automatic Pydantic validation, and built-in OpenAPI documentation reduce integration friction with the frontend significantly, especially under time pressure.

**Why in-memory state over a lightweight DB (SQLite, Redis)?**
Render's free tier does not include a managed database. SQLite on a free web service loses data on restart; adding Redis adds a separate paid service. For a single-session demo, an in-process dict is the correct tradeoff.

**Why OpenAI API (`gpt-5.4-mini` + `gpt-5.4`) instead of OpenRouter?**
The hackathon organiser sponsors $100 per account across 4 accounts ($400 total). This removes cost as a design constraint entirely. `gpt-5.4-mini` (released March 17, 2026) is used for Call 1 (intent parsing): it has a 400K context window, supports native JSON mode and function calling, and runs more than 2× faster than its predecessor — critical for the < 2s latency budget. `gpt-5.4` (released March 5, 2026) is used for Call 2 (insight generation): it is OpenAI's current frontier model with up to 1.05M context and significantly better prose quality, which directly improves the recommendation text judges read. At ≤1k tokens/request the total API cost per `/analyze` call is ~$0.003 — even 10,000 test runs = $30, well within the $400 budget.

**Why OLS + PLS-SEM instead of a single approach?**
SPSS-style OLS is universally understood and fast. PLS-SEM handles latent variables and is used in academic business research (the primary demo audience). Auto-selection removes the burden from the user — which is the core product differentiator.

**Why Vercel for frontend with no CLI?**
Vercel's GitHub integration is zero-configuration. Connecting the repo and pushing to `main` is the entire deployment workflow. The Vercel CLI adds no value here and introduces a setup step that can fail during a hackathon.

---

## 9. Open Points

| # | Question | Context | Options |
|---|---|---|---|
| OA-1 | Thread-safety of the in-memory `file_id` store | Python `dict` writes are not atomic under concurrent requests in multi-worker Uvicorn | (a) Accept single-worker limitation for demo; (b) Use `threading.Lock`; (c) Use `asyncio.Lock` |
| OA-2 | Render cold-start mitigation strategy | Free tier spins down after 15min inactivity; ~30s cold start would break the demo | (a) Pre-warm manually; (b) Use UptimeRobot ping every 14min (free); (c) Upgrade to paid |
| OA-3 | CORS origin configuration | Frontend URL is only known after first Vercel deploy | Set to `*` during development; update to exact Vercel URL before demo |
| OA-4 | `pyplspm` dependency stability | Library has limited maintenance; may conflict with `scipy` version | (a) Use only if custom PLS fails; (b) Implement minimal PLS from scratch with `numpy` |
| OA-5 | Maximum concurrent file uploads | In-memory dict grows unbounded if many files are uploaded | (a) Cap at 10 entries with LRU eviction; (b) Accept unbounded growth for demo only |
| OA-6 | Which OpenAI account key to use as primary | 4 keys available; rate limits are per-key | (a) Designate one key as primary, others as fallback rotation; (b) Round-robin across all 4 |

---

## 10. Related Documents

| Document | Path | Status |
|---|---|---|
| **Product Requirements** | `.docs/01-prd.md` | `draft` |
| **Codebase Summary** | `.docs/03-codebase-summary.md` | Not yet created |
| **ADRs** | `.docs/adrs/` | Not yet created |
| **Feature Specs** | `.docs/03-features-spec.md` | `draft` |
