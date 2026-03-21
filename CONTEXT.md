# SOTA StatWorks — Technical Context (Consolidated)

> **Auto-generated:** 2026-03-21  
> **Sources:** `.docs/01-prd.md`, `.docs/02-system-design.md`, `.docs/03-features-spec.md`, `.docs/04-rule.md`, `.docs/more/adrs/`, and implemented features not yet in docs.

---

## 1. Product Identity

| Field | Value |
|---|---|
| **Product** | SOTA StatWorks |
| **Team** | Phú Nhuận Builder × SOTA Works |
| **Tagline** | *"From Data to Decisions — Instantly."* |
| **One-liner** | AI-powered decision engine that transforms raw data into actionable insights and simulations — without requiring statistical expertise. |
| **Hackathon** | LotusHacks × HackHarvard × GenAI Fund Vietnam 2026 · Enterprise Track by TinyFish |
| **License** | AGPL-3.0 |

| Name | Role |
|------|------|
| **Nguyễn Ngọc Gia Bảo** | Team Leader · Fullstack Dev |
| **Đặng Đình Tiến** | UI/UX Advisor · Tester |
| **Đỗ Phúc Duy** | Tester · Pitching Personnel |

**Primary users:** Business analysts, product managers, marketers, economics students, researchers — anyone who holds structured data and needs to understand *what drives* a key outcome without SPSS/SmartPLS expertise.

**Core differentiators:**
- vs. SPSS: AI auto-selects the model; outputs decisions, not coefficient tables
- vs. SmartPLS: Chat-driven, zero setup, business-friendly language
- vs. Generic AI (ChatGPT): Real statistical computation (OLS, PLS-SEM) + built-in scenario simulation

---

## 2. Tech Stack

### Backend

| Technology | Purpose |
|---|---|
| Python 3.11+ | Runtime |
| FastAPI | Async web framework, auto OpenAPI docs |
| NumPy + SciPy + Pandas | Statistical computation (OLS, bootstrap, PLS) |
| OpenPyXL | Excel file parsing engine |
| python-docx / python-pptx | Context text extraction from Word/PowerPoint |
| OpenAI SDK (`openai`) | LLM integration — `gpt-5.4-mini` (Call 1) + `gpt-5.4` (Call 2) |
| Supabase (`supabase-py`) | PostgreSQL metadata storage |
| Cloudflare R2 (`boto3`) | S3-compatible object storage |
| Clerk | Authentication (header-based, no backend SDK) |
| ReportLab | PDF report generation |

### Frontend

| Technology | Purpose |
|---|---|
| Next.js 16 (App Router, Turbopack) | React framework |
| React 19 + TypeScript 5 | UI library + type safety |
| Tailwind CSS 4 | Styling |
| Zustand 5 | Global state management |
| TanStack React Query 5 | Server state / mutations |
| Recharts 3 | Data visualization (driver charts) |
| Framer Motion 12 | Animations (bar grow, count-up, panel reveal) |
| Clerk (`@clerk/nextjs`) | Authentication UI |
| SheetJS (xlsx) | Client-side spreadsheet parsing |

### Infrastructure

| Service | Purpose | Free Tier |
|---|---|---|
| Render.com | Backend hosting | 512 MB RAM, cold-start ~30s |
| Vercel | Frontend hosting (auto-deploy on push to `main`) | Hobby tier |
| Supabase | PostgreSQL metadata | 500 MB |
| Cloudflare R2 | Object storage | 10 GB, zero egress |
| Clerk | Auth (Google OAuth) | 10K MAU |
| OpenAI API | LLM calls | $100/account × 4 accounts = $400 budget |

---

## 3. Architecture

### High-Level Flow

```
[Browser / Next.js on Vercel]
    │
    ├── Login ──→ [Clerk] ──→ clerk_user_id
    │
    ├── POST /api/upload ──→ [FastAPI on Render]
    │       ├── Parse file (pandas)
    │       ├── Store DataFrame in-memory
    │       ├── Upload to R2 (async)
    │       └── Save metadata in Supabase (async)
    │
    ├── POST /api/chat/analyze ──→ [FastAPI]
    │       ├── LLM Call 1: gpt-5.4-mini ──→ intent + variables (JSON mode)
    │       ├── Validation Layer: strip hallucinated columns
    │       ├── Decision Router: score_pls vs score_reg
    │       ├── Statistical Engine: OLS or PLS-SEM
    │       ├── LLM Call 2: gpt-5.4 ──→ business summary + recommendation
    │       └── Return AnalyzeResponse (always 200)
    │
    ├── POST /api/monitor/simulate ──→ [FastAPI]
    │       ├── Load coefficient cache from memory
    │       ├── Build directed graph, DFS propagation
    │       └── Return impacts (deterministic, no LLM)
    │
    └── GET /api/history/export-pdf ──→ [FastAPI]
            ├── Collect history entries
            ├── LLM analysis (gpt-5.4-mini)
            └── ReportLab → PDF stream
```

### Component Responsibilities

| Component | Owns | Exposes |
|---|---|---|
| **API Gateway** | Routing, Pydantic validation, CORS | HTTP endpoints under `/api/*` |
| **Data Ingestion** | File parsing, column detection, in-memory store | `DataFrame`, `file_id`, column metadata |
| **AI Layer** | Prompt construction, LLM calls, retry/rotation | `ParsedIntent`, `InsightText` |
| **Validation Layer** | Schema enforcement on LLM output, fallback selection | Cleaned `ParsedIntent` |
| **Decision Router** | Model scoring, engine selection | Engine choice (`regression` / `pls`) |
| **Regression Engine** | OLS β, R², bootstrap p-values | `DriverResult[]`, `R²` |
| **PLS Engine** | Latent variable scoring, path coefficients | `DriverResult[]`, `R²` |
| **Simulation Engine** | DFS graph propagation | `SimulationResult` |
| **History Store** | In-memory autosave for Chat/Viewer/Monitor | `HistoryEntry[]` |

### Three-Layer Storage Model

| Layer | Technology | Purpose |
|---|---|---|
| In-memory cache | Python `OrderedDict` (LRU, 10 entries) | Fast access to latest DataFrame + coefficient cache |
| Metadata store | Supabase (PostgreSQL) | Persistent: users, datasets, analyses, conversations |
| Object store | Cloudflare R2 | Raw files (.csv, .xlsx), analysis output (.json) |

---

## 4. API Surface

All endpoints under `/api/*` prefix, grouped by feature:

### Upload (`/api/upload`)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/upload` | Upload files (multipart), returns `file_id`, columns, row_count |
| `POST` | `/api/upload/presign` | Get R2 presigned upload URL |

**Constraints:** Max 5 files/request, max 20 MB/file, 1 primary data file (.xlsx/.csv), optional context files (.docx/.pptx).

### AI Chat (`/api/chat`)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/chat/analyze` | Full 2-call LLM pipeline → AnalyzeResponse |
| `GET` | `/api/chat/conversations` | List user's conversations |
| `POST` | `/api/chat/conversations` | Create new conversation |
| `GET` | `/api/chat/conversations/{id}/messages` | Get messages for a conversation |
| `POST` | `/api/chat/conversations/{id}/messages` | Add message to conversation |

### Data Viewer (`/api/data`)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/data/{id}/content` | Get file content as JSON |
| `PATCH` | `/api/data/{id}/cells` | Update cell values (in-place edit) |

### Monitor (`/api/monitor`)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/monitor/simulate` | What-if simulation (DFS graph propagation) |

### History (`/api/history`)

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/history` | List history entries (with category + date filters) |
| `POST` | `/api/history` | Save history entry |
| `GET` | `/api/history/{id}` | Get single history entry |
| `GET` | `/api/history/export-pdf` | Generate AI-analyzed PDF report |

### Auth (`/api/auth`)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/auth/sync-user` | Sync Clerk user to Supabase |

### Health

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/health` | Health check (pre-warm on demo) |

---

## 5. AnalyzeResponse Schema (Core Data Contract)

```json
{
  "summary": "Trust is the strongest driver of customer retention.",
  "drivers": [
    { "name": "Trust",  "coef": 0.62, "p_value": 0.001, "significant": true },
    { "name": "UX",     "coef": 0.34, "p_value": 0.023, "significant": true },
    { "name": "Price",  "coef": 0.08, "p_value": 0.412, "significant": false }
  ],
  "r2": 0.48,
  "recommendation": "Focus resources on improving Trust — it delivers the highest return on retention.",
  "model_type": "regression",
  "decision_trace": {
    "score_pls": 0.21,
    "score_reg": 0.54,
    "engine_selected": "regression",
    "reason": "Dataset has fully observable numeric columns; no latent variable indicators detected."
  }
}
```

**Rules:** Max 5 drivers, sorted by `|coef|` descending. `summary` and `recommendation` never contain statistical jargon. `drivers` always uses validated column names (never hallucinated). HTTP status is always 200 — errors are wrapped, not raised.

---

## 6. LLM Pipeline

### Architecture

```
User Query + Dataset Columns
    │
    ▼
[LLM Call 1]  gpt-5.4-mini (JSON mode)
    → { intent, target, features, group_by, edits, not_supported_reason }
    │
    ▼
[Validation Layer]  strip hallucinated columns, auto-detect target/features
    │
    ▼
[Statistical Engine]  OLS or PLS (Decision Router selects)
    │
    ▼
[LLM Call 2]  gpt-5.4 (frontier model)
    → { summary, recommendation }
    │
    ▼
AnalyzeResponse (JSON)
```

### Models & Costs

| Call | Model | Cost/request | Context | Purpose |
|---|---|---|---|---|
| 1 | `gpt-5.4-mini` | ~$0.00075 | 400K tokens | Intent parsing, variable extraction |
| 2 | `gpt-5.4` | ~$0.0025 | 272K–1.05M tokens | Business insight generation |

**Total per `/analyze`**: ~$0.003. Budget: $400 (unconstrained for demo).

### System Prompts (Centralized in `backend/llm/prompts.py`)

| Prompt | Call Site | Key Features |
|---|---|---|
| `SYSTEM_PROMPT_PARSE` | `parser.py` → gpt-5.4-mini | Project identity, scope enforcement, refusal logic, Vietnamese+English bilingual, data editing format rules |
| `SYSTEM_PROMPT_INSIGHT` | `insight.py` → gpt-5.4 | Jargon ban (30+ forbidden terms), language-adaptive responses, ranking enforcement, CEO-friendly tone |
| `SYSTEM_PROMPT_REPORT` | `main.py:export_pdf` → gpt-5.4-mini | Session synthesis structure, bilingual, no jargon |

### Intents (Call 1 Output)

| Intent | Triggers |
|---|---|
| `driver_analysis` | "What affects X?", "Yếu tố nào ảnh hưởng đến X?" |
| `comparison` | "Compare A vs B", "So sánh theo khu vực" |
| `summary` | "Summarize the data", "Tổng quan dữ liệu" |
| `general_question` | Data question that doesn't fit above |
| `data_edit` | "Change X to Y", "Sửa ngày thành DD/MM/YYYY" |
| `not_supported` | Off-topic, greeting, general knowledge |

### Key Rotation

4 OpenAI API keys (`OPENAI_API_KEY_1` → `4`). On `RateLimitError`, `_rotate_client()` advances round-robin. Max 3 total attempts (1 initial + 2 retries), 500ms backoff.

### 4-Layer Fallback Chain

| Layer | Trigger | Fallback |
|---|---|---|
| 1 | LLM Call 1 fails | Auto-detect: target = last column, features = all numeric |
| 2 | PLS engine fails | Re-run with OLS regression |
| 3 | OLS engine fails | Return `{drivers: [], summary: "Insufficient data..."}` |
| 4 | LLM Call 2 fails | Template: "{top_driver} shows the strongest relationship..." |

**The system NEVER crashes. Every request returns HTTP 200 with a valid body.**

---

## 7. Statistical Engines

### OLS Regression

- **Method:** `β = np.linalg.lstsq(X, y)` (numerically stable)
- **R²:** `1 - (SS_res / SS_tot)`
- **P-values:** Bootstrap with `np.random.default_rng(seed=42)`, max 200 samples
- **Significance:** `p < 0.05`

### PLS-SEM (Simplified)

- **Latent variable:** `LV = df[indicators].mean(axis=1)` (not full NIPALS/SIMPLS)
- **Path coefficients:** Same OLS on latent variables
- **Decision threshold:** Selected only when `score_pls > score_reg`

### Decision Router Scoring

```
score_pls = 0.4·L + 0.3·M + 0.3·C
score_reg = 0.6·O + 0.4·(1−C)

L = latent variable presence
M = multi-item indicator count
C = complexity
O = all-numeric observability
```

### Simulation Engine

- **Method:** DFS on directed coefficient graph
- **1-hop:** `ΔY = β · ΔX`
- **Multi-hop:** `ΔZ = β_XZ·ΔX + β_YZ·(β_XY·ΔX)` (additive across paths)
- **Cycle protection:** `visited` set prevents infinite recursion
- **No LLM call.** Purely deterministic.

---

## 8. Frontend Architecture

### Navigation

Canva-inspired vertical sidebar (68px collapsed, 200px expanded) with 5 views + user account (ADR-0004):

| # | View | Path | Gate |
|---|---|---|---|
| 1 | Upload | `/app` | Always active |
| 2 | AI Chat | `/app/chat` | Requires uploaded data |
| 3 | Data Viewer | `/app/viewer` | Requires uploaded data |
| 4 | Monitor | `/app/monitor/*` | Requires uploaded data |
| 5 | History | `/app/history/*` | Always active |
| 6 | Account | — | Always active (sidebar bottom) |

### State Management

**Zustand** for global UI state:

```typescript
interface AppStore {
  user: ClerkUser | null
  fileId: string | null
  datasetName: string | null
  rowCount: number | null
  columns: Column[]
  insight: InsightResult | null
  simulation: SimulationResult | null
  isAnalyzing: boolean
  isSimulating: boolean
  isUploading: boolean
}
```

**React Query** for server-state mutations (analyze, simulate, upload).

### Key Frontend Components

| Component | Purpose |
|---|---|
| `UploadZone` | Drag-and-drop / click file upload |
| `ChatPanel` | Message input + suggested prompts |
| `InsightPanel` | SummaryCard → DriverChart → RecommendationCard |
| `SimulationBar` | Variable select + delta slider + simulate button |
| `DataViewer` | Browser-tab file viewer with in-place cell editing |
| `Monitor` | SPSS/SmartPLS ribbon dashboard |
| `HistoryView` | 3-tab (Chat/Viewer/Monitor) history with time filters |

### Animation Strategy (WOW factor)

- Bar grow on DriverChart
- Count-up on SimulationResult badges
- Progressive reveal: SummaryCard → DriverChart → RecommendationCard (fade-in)
- Sidebar expand/collapse on hover

---

## 9. Authentication & Persistence

### Auth Flow (ADR-0001)

1. User clicks "Sign in with Google" → Clerk handles OAuth
2. Frontend: `useUser()` → `{ id, firstName, imageUrl }`
3. All API calls include `x-clerk-user-id` header
4. Backend extracts `clerk_user_id` from header (no Clerk SDK server-side)
5. On first login: create user record in Supabase

### Supabase Tables (ADR-0002)

```sql
-- users
id uuid PK, clerk_user_id text UNIQUE, email text, name text, created_at timestamp

-- datasets
id uuid PK, user_id uuid FK, file_name text, r2_key text, created_at timestamp

-- analyses
id uuid PK, dataset_id uuid FK, result jsonb, created_at timestamp

-- conversations (ADR-0005)
id uuid PK, user_id text, title text, created_at timestamptz, updated_at timestamptz

-- messages
id uuid PK, conversation_id uuid FK, role text ('user'|'assistant'), content jsonb, created_at timestamptz

-- conversation_files
conversation_id uuid FK, dataset_id text, PK(conversation_id, dataset_id)
```

### R2 Bucket Layout (ADR-0003)

```
bucket/users/{clerk_user_id}/datasets/{dataset_id}.csv
bucket/users/{clerk_user_id}/outputs/{analysis_id}.json
```

All access via time-limited presigned URLs. Zero egress fees.

### Graceful Degradation

If Clerk/Supabase/R2 are unreachable, the app falls back to in-memory-only mode (no persistence, no auth). Analysis still works.

---

## 10. History System (ADR-0006)

### In-Memory Autosave

- **Store:** `dict[user_id][category] → list[HistoryEntry]` with `threading.Lock` for concurrency
- **Categories:** Chat, Data Viewer, Dashboard/Monitor
- **Eviction:** LRU at 200 entries per category per user
- **Persistence:** In-memory only (lost on restart — acceptable for demo)

### History Entry Model

```python
@dataclass
class HistoryEntry:
    id: str                    # UUID
    user_id: str               # clerk_user_id
    category: str              # "chat" | "viewer" | "monitor"
    title: str                 # Auto-generated summary
    snapshot: dict              # Full data snapshot
    created_at: str            # ISO 8601
    metadata: dict | None       # Optional extra context
```

### PDF Export (ADR-0007)

1. Collect all history entries (with date range filter)
2. Send to `gpt-5.4-mini` for session synthesis
3. ReportLab generates A4 PDF (Helvetica font, #2D3561 header colors)
4. Stream back as `application/pdf` download
5. Fallback: "AI analysis unavailable. Raw session data included below."

---

## 11. Features Summary (F-01 through F-09)

| # | Feature | Endpoint(s) | Status |
|---|---|---|---|
| F-01 | Data Ingestion | `POST /api/upload` | Implemented |
| F-02 | AI-Powered Driver Analysis | `POST /api/chat/analyze` | Implemented |
| F-03 | Scenario Simulation | `POST /api/monitor/simulate` | Implemented |
| F-04 | Frontend — Sidebar Navigation | Next.js App Router | Implemented |
| F-05 | Authentication & Identity | Clerk + Supabase + R2 | Implemented |
| F-06 | Data Viewer | `GET/PATCH /api/data/{id}/*` | Implemented |
| F-07 | SPSS/SmartPLS Dashboard | Wraps analyze + simulate | Implemented |
| F-08 | Upload History | `GET /datasets` | Implemented |
| F-09 | Chat History | `GET/POST /api/chat/conversations` | Implemented |

### Undocumented Implementations (beyond .docs/)

| Feature | File(s) | Description |
|---|---|---|
| Centralized GPT System Prompts | `backend/llm/prompts.py` | 3 prompts with project identity, scope enforcement, refusal logic, Vietnamese bilingual support |
| In-Memory History Store | `backend/history_store.py` | Thread-safe autosave with LRU eviction, date-range filtering, export support |
| PDF Export | `backend/main.py:export_pdf` | LLM-analyzed session report → ReportLab A4 PDF |
| Route Conflict Fix | `backend/main.py` | `/api/history/export-pdf` registered BEFORE `/api/history/{entry_id}` |
| Safe User Hook | `frontend/components/data-viewer.tsx` | `useSafeUser()` prevents crash when ClerkProvider unavailable |
| SSR Fallback URL | `frontend/lib/api.ts` | `getBaseUrl()` returns `http://localhost:8000` instead of throwing on missing env |

---

## 12. Backend Module Map

```
backend/
├── main.py              # FastAPI app, CORS, all routers, export-pdf, history endpoints
├── config.py            # Env var loading, DEV_MODE flag, key pool, CORS config
├── models.py            # Pydantic models: AnalyzeRequest/Response, UploadResponse, etc.
├── store.py             # In-memory OrderedDict with asyncio.Lock (LRU 10 entries)
├── upload.py            # POST /upload — file parsing, column detection, R2 + Supabase
├── analyze.py           # POST /analyze — full 2-call LLM pipeline (960 lines)
├── simulate.py          # POST /simulate — DFS graph propagation
├── router.py            # Decision Router scoring (score_pls vs score_reg)
├── validation.py        # Validation Layer — strip LLM hallucinations, auto-detect
├── history_store.py     # In-memory history autosave with threading.Lock
├── auth/
│   └── context.py       # Extract clerk_user_id from request headers
├── db/
│   └── supabase.py      # Supabase client, metadata CRUD
├── engines/
│   ├── regression.py    # OLS computation, bootstrap p-values
│   ├── pls.py           # PLS-SEM (simplified: LV = mean of indicators)
│   └── simulation.py    # DFS impact propagation
├── llm/
│   ├── client.py        # AsyncOpenAI pool, key rotation, call_llm_with_retry()
│   ├── parser.py        # LLM Call 1: parse_user_intent() via gpt-5.4-mini
│   ├── insight.py       # LLM Call 2: generate_insight() via gpt-5.4
│   └── prompts.py       # Centralized system prompts (PARSE, INSIGHT, REPORT)
├── storage/
│   └── r2.py            # Cloudflare R2 client (boto3, presigned URLs)
└── tests/               # 20 test functions, 143 assertions
```

---

## 13. Environment Variables

### Backend (`backend/.env` / Render dashboard)

| Variable | Required | Purpose |
|---|---|---|
| `OPENAI_API_KEY_1` | Yes (prod) | Primary OpenAI API key |
| `OPENAI_API_KEY_2..4` | No | Rotation pool (on RateLimitError) |
| `DEV_MODE` | No | Default `true`. Set `false` in production |
| `SUPABASE_URL` | No | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | No | Supabase service role key |
| `R2_ACCOUNT_ID` | No | Cloudflare account ID |
| `R2_ACCESS_KEY_ID` | No | R2 access key |
| `R2_SECRET_ACCESS_KEY` | No | R2 secret key |
| `R2_BUCKET_NAME` | No | R2 bucket name |
| `CORS_ORIGIN` | No | Comma-separated origins (default `*`) |
| `CLERK_SECRET_KEY` | No | Clerk secret (if JWT verification needed) |

### Frontend (`frontend/.env.local` / Vercel dashboard)

| Variable | Required | Purpose |
|---|---|---|
| `NEXT_PUBLIC_BACKEND_URL` | Yes | Backend URL (e.g., `https://statworks-api.onrender.com`) |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key |
| `CLERK_SECRET_KEY` | Yes | Clerk secret key |

---

## 14. Performance Budget

| Target | Mechanism |
|---|---|
| `/analyze` < 2s | Bootstrap ≤ 200 samples; LLM token ≤ 1k/call; in-process computation |
| `/simulate` < 1s | Cached coefficients; DFS on < 20 nodes; no LLM |
| Upload < 3s | pandas parse + async R2 upload |
| Tab switch < 100ms | In-memory data, client-side rendering |
| Max 2 LLM calls per `/analyze` | No chain-of-thought, no intermediate calls |
| Render cold-start | Pre-warm via `GET /api/health` before demo |

---

## 15. Security Model

- **Auth:** Clerk Google OAuth → `x-clerk-user-id` header → backend extracts, no Clerk SDK
- **CORS:** Restricted to Vercel origin in production
- **API keys:** Environment variables only, never committed
- **R2:** Private bucket, presigned URLs only (time-limited)
- **LLM output:** Always through Validation Layer before computation
- **Pydantic:** All request bodies validated at boundary
- **RLS:** Supabase Row Level Security available (optional for v1)

---

## 16. Architecture Decision Records (ADRs)

| ADR | Decision | Status |
|---|---|---|
| ADR-0001 | Clerk for authentication (Google OAuth, prebuilt UI, 10K MAU free) | proposed |
| ADR-0002 | Supabase for metadata persistence (PostgreSQL, JSONB, 500MB free) | proposed |
| ADR-0003 | Cloudflare R2 for object storage (S3-compatible, zero egress, 10GB free) | proposed |
| ADR-0004 | Canva-inspired sidebar navigation (68px collapsed → 200px expanded, 5 views) | proposed |
| ADR-0005 | Chat history via Supabase (conversations + messages + join tables) | proposed |
| ADR-0006 | In-memory history autosave (zero-latency, LRU 200 entries, lost on restart) | proposed |
| ADR-0007 | PDF export via ReportLab + LLM analysis (server-side, A4, branded styles) | proposed |

---

## 17. Key Engineering Rules

### API Design
- All endpoints under `/api/*` prefix
- Always return `application/json` body (including errors)
- Use HTTP status codes exactly: 200, 404, 409, 413, 415, 422
- Never use `400` as catch-all

### Python
- Python 3.11+, `from __future__ import annotations`
- All functions must have type hints
- OLS via `np.linalg.lstsq` (never explicit matrix inversion)
- Bootstrap seed = 42 (reproducible)
- `asyncio.Lock` protecting in-memory store
- Use `openai` SDK, not raw `requests`

### LLM
- Call 1: `gpt-5.4-mini` only (JSON mode)
- Call 2: `gpt-5.4` only
- Max 2 LLM calls per `/analyze`
- System prompt must enforce strict JSON schema
- Key rotation order: `KEY_1 → KEY_2 → KEY_3 → KEY_4`
- Jargon ban: 30+ statistical terms forbidden in user-facing text

### Frontend
- `strict: true` in tsconfig.json
- No `any` type — use `unknown` and narrow
- All API responses explicitly typed
- Zustand for global state, React Query for server state
- `NEXT_PUBLIC_BACKEND_URL` from env var (no hardcoded URLs)

### Error Handling
- **System never crashes.** 4-layer fallback chain ensures valid response always.
- All endpoints `async def`
- LLM retry ×2 with 500ms backoff
- PLS → OLS fallback on engine failure
- Template strings as final fallback for insight generation

---

## 18. Deployment

### Backend (Render.com)

```yaml
# render.yaml
services:
  - type: web
    name: statworks-api
    runtime: python
    plan: free
    buildCommand: pip install -r backend/requirements.txt
    startCommand: python -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DEV_MODE
        value: "false"
```

### Frontend (Vercel)

- Auto-deploy on push to `main`
- Environment variables set in Vercel dashboard
- No Vercel CLI, no serverless functions
- All compute on Render backend

---

## 19. Data Flow Diagrams

### Upload → Analyze → Simulate (Happy Path)

```
1. User drags data.xlsx onto UploadZone
   → POST /api/upload (multipart)
   → file_id returned, DataFrame cached in memory
   → File uploaded to R2, metadata saved to Supabase (async)

2. User types "What affects retention?"
   → POST /api/chat/analyze { file_id, query }
   → LLM Call 1 (gpt-5.4-mini): { intent: "driver_analysis", target: "Retention", features: ["Trust","UX","Price"] }
   → Validate: strip invalid columns, verify target
   → Decision Router: score_reg > score_pls → OLS
   → OLS: β = [0.62, 0.34, 0.08], R² = 0.48
   → LLM Call 2 (gpt-5.4): { summary: "Trust is the strongest...", recommendation: "Focus on Trust..." }
   → Return AnalyzeResponse
   → Cache coefficient_map under file_id
   → Save to Supabase (async)

3. User selects Trust +20% in SimulationBar
   → POST /api/monitor/simulate { file_id, variable: "Trust", delta: 0.20 }
   → Load coefficient_map from cache
   → DFS: ΔRetention = 0.62 × 0.20 = 0.124 → 12.4%
   → Return { impacts: [{ variable: "Retention", delta_pct: 12.4 }] }
```

### Off-Topic Query (Refusal)

```
User types "What is the capital of France?"
→ POST /api/chat/analyze { file_id, query }
→ LLM Call 1: { intent: "not_supported", not_supported_reason: "This question is not related to your dataset..." }
→ Return 200 with not_supported response (no statistical computation)
```

---

## 20. File Size & Complexity Reference

| File | Lines | Purpose |
|---|---|---|
| `backend/analyze.py` | ~960 | Full AI pipeline with all fallback layers |
| `backend/main.py` | ~700 | FastAPI app, routers, history, export-pdf |
| `backend/llm/prompts.py` | ~180 | Centralized GPT system prompts |
| `backend/upload.py` | ~280 | File parsing, R2 upload, Supabase save |
| `backend/store.py` | ~170 | In-memory OrderedDict with asyncio.Lock |
| `backend/history_store.py` | ~180 | Thread-safe history autosave |
| `frontend/app/page.tsx` | ~470 | Landing page (hero, features, comparison) |
| `frontend/globals.css` | ~1200 | Full design system |
