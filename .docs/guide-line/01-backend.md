# SOTA StatWorks — Backend Guide

| Field            | Value                            |
|------------------|----------------------------------|
| **Last updated** | 2026-03-21                       |
| **Version**      | 0.2.0                            |
| **Stack**        | Python 3.11+ · FastAPI · numpy · pandas · supabase · boto3 |
| **Source**       | `backend/` directory             |

---

## 1. Quick Start

```bash
# Install (from project root)
cd backend && pip install -e .

# Run dev server (from project root)
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests (from project root)
python -m pytest backend/tests/ -v
```

> **Note:** `.env` is auto-loaded from `backend/.env` via `python-dotenv`. Copy the template first: `cp backend/.env.example backend/.env`

---

## 2. Project Structure

```
backend/
├── pyproject.toml          # Package config + dependencies
├── .env.example            # Env var template (safe to commit)
├── .env                    # Active credentials (gitignored)
├── __init__.py
├── main.py                 # FastAPI app, CORS, /health, /datasets, router registration
├── config.py               # Env var reader + python-dotenv auto-load
├── store.py                # In-memory OrderedDict store (LRU, asyncio.Lock)
├── models.py               # All Pydantic models (request/response shapes)
├── upload.py               # POST /upload, POST /upload/presign
├── analyze.py              # POST /analyze — stat engine orchestration + Supabase persist
├── simulate.py             # POST /simulate — graph DFS propagation
├── router.py               # Decision Router (PLS vs regression scoring)
├── validation.py           # Validation Layer (sanitises LLM output before engines)
├── auth/
│   ├── __init__.py
│   └── context.py          # get_current_user_id() — Clerk header extraction
├── db/
│   ├── __init__.py
│   └── supabase.py         # Supabase CRUD (users, datasets, analyses)
├── storage/
│   ├── __init__.py
│   └── r2.py               # Cloudflare R2 via boto3 (presigned URLs, upload/download)
├── engines/
│   ├── __init__.py
│   ├── regression.py       # OLS via np.linalg.lstsq + bootstrap p-values
│   ├── pls.py              # Simplified PLS (mean-LV) + PLSFallbackError
│   └── simulation.py       # Directed graph builder + DFS delta propagation
├── supabase/
│   └── migrations/         # Supabase CLI migration files
│       └── 20260320..._create_tables.sql
└── tests/
    ├── __init__.py
    └── test_backend.py     # 20 test functions, 143 assertions
```

---

## 3. API Reference

### `GET /health`
Health check for uptime monitors and Render pre-warming.

| Field    | Value            |
|----------|------------------|
| Response | `{"status":"ok"}` |
| Status   | `200`            |

---

### `POST /upload`
Accepts multipart form-data with one or more files. Persists to R2 + Supabase async if user is authenticated.

**Rules:**
- Exactly 1 primary file (`.xlsx` or `.csv`) required
- Optional context files (`.docx`, `.pptx`) — text extraction only
- Max file size: **10 MB**

| Status | Condition                     |
|--------|-------------------------------|
| `200`  | Success                       |
| `413`  | File > 10 MB                  |
| `415`  | Unsupported extension         |
| `422`  | Multiple primary files / none |

**Response (200):**
```json
{
  "file_id": "uuid-v4",
  "columns": [{"name": "Trust", "dtype": "float64", "is_numeric": true}],
  "row_count": 120,
  "context_extracted": false
}
```

---

### `POST /upload/presign`
Generate a presigned R2 upload URL for direct frontend upload. **Requires `x-clerk-user-id` header.**

**Request:** `{"file_name": "data.csv"}`

| Status | Condition            |
|--------|----------------------|
| `200`  | Success              |
| `401`  | Missing auth header  |
| `503`  | R2 not configured    |

**Response (200):**
```json
{
  "upload_url": "https://...r2.cloudflarestorage.com/...",
  "r2_key": "users/clerk_123/datasets/uuid.csv"
}
```

---

### `POST /analyze`
Runs statistical analysis on an uploaded dataset. Persists results to Supabase async.

**Request:** `{"file_id": "...", "query": "What affects retention?"}`

| Status | Condition                 |
|--------|---------------------------|
| `200`  | Success (always valid body)|
| `404`  | Unknown `file_id`         |
| `422`  | Missing required fields   |
| `500`  | Unexpected server error   |

**Response (200):**
```json
{
  "summary": "Trust is the strongest driver of retention.",
  "drivers": [{"name": "Trust", "coef": 0.62, "p_value": 0.001, "significant": true}],
  "r2": 0.48,
  "recommendation": "Focus on improving Trust.",
  "model_type": "regression",
  "decision_trace": {
    "score_pls": 0.21, "score_reg": 0.54,
    "engine_selected": "regression",
    "reason": "Dataset has fully observable numeric columns."
  }
}
```

---

### `POST /simulate`
Propagates a variable change through the coefficient graph.

**Request:** `{"file_id": "...", "variable": "Trust", "delta": 0.20}`

| Status | Condition                           |
|--------|-------------------------------------|
| `200`  | Success                             |
| `404`  | Unknown `file_id`                   |
| `409`  | `/analyze` not called yet           |
| `422`  | Invalid variable (lists valid ones) |

---

### `GET /datasets`
Lists all datasets for the authenticated user. **Requires `x-clerk-user-id` header.**

| Status | Condition           |
|--------|---------------------|
| `200`  | Success (may be []) |
| `401`  | Missing auth header |

---

## 4. Environment Variables

| Variable               | Required  | Default | Description                          |
|------------------------|-----------|---------|--------------------------------------|
| `DEV_MODE`             | No        | `true`  | Skip API key validation in dev       |
| `CORS_ORIGIN`          | No        | `*`     | Allowed CORS origin                  |
| `OPENAI_API_KEY_1`–`4` | Prod only | —       | OpenAI keys (4-key rotation)         |
| `SUPABASE_URL`         | No        | —       | Supabase project URL                 |
| `SUPABASE_SERVICE_KEY`  | No        | —       | Supabase service role key            |
| `R2_ACCOUNT_ID`        | No        | —       | Cloudflare account ID                |
| `R2_ACCESS_KEY_ID`     | No        | —       | R2 API token access key              |
| `R2_SECRET_ACCESS_KEY` | No        | —       | R2 API token secret                  |
| `R2_BUCKET_NAME`       | No        | —       | R2 bucket name                       |
| `CLERK_SECRET_KEY`     | No        | —       | Clerk backend secret key             |

> All Supabase/R2/Clerk vars are **optional**. Missing → warning log, graceful degradation to in-memory-only mode.

---

## 5. Architecture Flow

```
Upload → Store DataFrame in memory → Async: R2 upload + Supabase metadata
                    ↓
Analyze → Validation → Decision Router → Stat Engine → Store coefficients
                    ↓                          ↓          ↓
              (Phase 2: LLM)            Async: Supabase persist
                    ↓
Simulate → Read cached coefficients → Build graph → DFS propagate → Return impacts
```

### Graceful Degradation

| Service  | Missing env vars    | Behaviour                          |
|----------|---------------------|------------------------------------|
| Supabase | `SUPABASE_URL`      | Warning log, in-memory only        |
| R2       | `R2_ACCOUNT_ID`     | Warning log, no file persistence   |
| Clerk    | `CLERK_SECRET_KEY`  | Anonymous mode, all users = None   |

### Fallback Chain (4 layers — never crash)

| Layer | Trigger              | Fallback                                 |
|-------|----------------------|------------------------------------------|
| 1     | LLM Call 1 fails     | Auto-select all numeric columns          |
| 2     | PLS engine fails     | Fall back to OLS regression              |
| 3     | OLS also fails       | Return `drivers: [], r2: null`           |
| 4     | LLM Call 2 fails     | Template string summary                  |

---

## 6. Key Design Decisions

| Decision | Choice | Reference |
|---|---|---|
| Authentication | Clerk — header extraction only, no SDK | [ADR-0001](.docs/more/adrs/0001-clerk-authentication.md) |
| Metadata DB | Supabase (PostgreSQL) | [ADR-0002](.docs/more/adrs/0002-supabase-metadata.md) |
| Object storage | Cloudflare R2 (S3-compatible, zero egress) | [ADR-0003](.docs/more/adrs/0003-cloudflare-r2-storage.md) |
| OLS solver | `np.linalg.lstsq` | Numerically stable; never `np.linalg.inv` |
| Bootstrap | `seed=42`, max 200 samples | Reproducible, within 2s latency budget |
| Async persistence | `asyncio.create_task` + `run_in_executor` | Fire-and-forget, never blocks response |
| Column names | Strip whitespace, **don't** lowercase | Preserves casing for LLM matching |

---

## 7. Testing

The test suite at `backend/tests/test_backend.py` covers **143 assertions** across **20 test functions**:

| Group | What it covers |
|---|---|
| Health | Status code + body shape |
| Upload — Happy | `.xlsx`, `.csv`, whitespace stripping, dtype detection |
| Upload — Errors | 415 (bad type), 413 (too large), 422 (multiple primary) |
| Upload — Edge | Single-row, NaN, mixed types, 25 columns, 0 rows, Unicode |
| LRU Eviction | 12 uploads → oldest 2 evicted |
| Analyze — Happy | Response shape, driver ordering, R² range, trace fields |
| Analyze — Errors | 404, 422 |
| Analyze — Edge | Single-col, all-string, NaN, 2-row, constant, reproducibility, 20-feature |
| Simulate — Happy | Positive/negative/zero delta, impact structure |
| Simulate — Errors | 404, 409, 422, missing fields |
| Simulate — Edge | Large delta, tiny delta, rounding |
| CORS | OPTIONS preflight |
| E2E Flow | upload → analyze → simulate |
| Auth Context | Header extraction, missing/empty header |
| R2 Module | Key generation, graceful degradation |
| Supabase Module | CRUD safe defaults when unavailable |
| Upload Presign | 401, 503, 422 |
| Datasets Endpoint | 401, 200, response shape |
| Upload with Auth | Works with and without auth |
| Auth E2E | Full authenticated flow with 4 steps |

```bash
# Run via pytest
python -m pytest backend/tests/ -v

# Run standalone
python backend/tests/test_backend.py
```

---

## 8. Deployment (Render.com)

Config reference in `backend/render.yaml`:

```yaml
services:
  - type: web
    name: sota-statworks-api
    runtime: python
    buildCommand: pip install -r backend/requirements.txt
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
```

> **Important:** Root Directory must be **empty** (deploy from project root) because all Python imports use `from backend.xxx`.

**Pre-demo checklist:**
1. Set `DEV_MODE=false` in Render env vars
2. Set `CORS_ORIGIN` to exact Vercel URL
3. Set at least `OPENAI_API_KEY_1`
4. Set Supabase/R2/Clerk env vars for full persistence
5. Hit `GET /health` 5 min before demo to pre-warm
