# SOTA StatWorks — Backend Guide

| Field            | Value                            |
|------------------|----------------------------------|
| **Last updated** | 2026-03-20                       |
| **Stack**        | Python 3.11+ · FastAPI · numpy · pandas |
| **Source**       | `backend/` directory             |

---

## 1. Quick Start

```bash
# Install (from project root)
cd backend && pip install -e .

# Run dev server (from project root)
cd .. && DEV_MODE=true python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Run tests (from project root)
PYTHONPATH=. DEV_MODE=true python3 backend/tests/test_backend.py
```

> **Note:** Always start uvicorn from the **project root** (`sota-statworks-pro/`), not from inside `backend/`. The module path `backend.main:app` resolves relative to the working directory.

---

## 2. Project Structure

```
backend/
├── pyproject.toml          # Python package config + dependencies
├── __init__.py
├── main.py                 # FastAPI app entry point, CORS, /health, router registration
├── config.py               # Env var reader (API keys, CORS_ORIGIN, DEV_MODE)
├── store.py                # In-memory OrderedDict store (LRU, asyncio.Lock)
├── models.py               # All Pydantic models (request/response shapes)
├── upload.py               # POST /upload — file validation, parsing, dtype detection
├── analyze.py              # POST /analyze — stat engine orchestration + fallback chain
├── simulate.py             # POST /simulate — graph DFS propagation
├── router.py               # Decision Router (PLS vs regression scoring)
├── validation.py           # Validation Layer (sanitises LLM output before engines)
├── engines/
│   ├── __init__.py
│   ├── regression.py       # OLS via np.linalg.lstsq + bootstrap p-values
│   ├── pls.py              # Simplified PLS (mean-LV) + PLSFallbackError
│   └── simulation.py       # Directed graph builder + DFS delta propagation
├── llm/                    # (Phase 2) OpenAI SDK integration
│   ├── client.py           # AsyncOpenAI clients + key rotation
│   ├── parser.py           # LLM Call 1: intent parsing (gpt-5.4-mini)
│   └── insight.py          # LLM Call 2: insight generation (gpt-5.4)
└── tests/
    ├── __init__.py
    └── test_backend.py     # 118-assertion comprehensive test suite
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
Accepts multipart form-data with one or more files.

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

### `POST /analyze`
Runs statistical analysis on an uploaded dataset.

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
    "score_pls": 0.21,
    "score_reg": 0.54,
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
| `500`  | Unexpected server error             |

**Response (200):**
```json
{
  "variable": "Trust",
  "delta": 0.20,
  "impacts": [{"variable": "Retention", "delta_pct": 12.4}]
}
```

---

## 4. Environment Variables

| Variable             | Required     | Default | Description                       |
|----------------------|--------------|---------|-----------------------------------|
| `DEV_MODE`           | No           | `true`  | Skip API key validation in dev    |
| `CORS_ORIGIN`        | No           | `*`     | Allowed CORS origin               |
| `OPENAI_API_KEY_1`   | Prod only    | —       | Primary OpenAI key                |
| `OPENAI_API_KEY_2`   | No           | —       | Fallback key 2                    |
| `OPENAI_API_KEY_3`   | No           | —       | Fallback key 3                    |
| `OPENAI_API_KEY_4`   | No           | —       | Fallback key 4                    |

---

## 5. Architecture Flow

```
Upload → Store DataFrame in memory (keyed by file_id)
                    ↓
Analyze → Validation Layer → Decision Router → Stat Engine → Store coefficients
                    ↓                              ↓
              (Phase 2: LLM Call 1)         (Phase 2: LLM Call 2)
                    ↓                              ↓
           Parse intent + features        Generate insight text
                    ↓
Simulate → Read cached coefficients → Build graph → DFS propagate → Return impacts
```

### Fallback Chain (4 layers — never crash)

| Layer | Trigger                    | Fallback                                           |
|-------|----------------------------|-----------------------------------------------------|
| 1     | LLM Call 1 fails           | Auto-select all numeric columns, infer target        |
| 2     | PLS engine fails           | Fall back to OLS regression, update trace            |
| 3     | OLS also fails             | Return `drivers: [], r2: null` with message          |
| 4     | LLM Call 2 fails           | Template string: `"{driver} shows the strongest..."` |

---

## 6. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| OLS solver | `np.linalg.lstsq` | Numerically stable for near-singular matrices; never use `np.linalg.inv` |
| Bootstrap | `seed=42`, `n=200` max | Reproducible results; stays within 2s latency budget |
| PLS latent vars | `mean(indicators)` | Full NIPALS exceeds build window; mean-LV is defensible for demo |
| In-memory store | `OrderedDict` + `asyncio.Lock` | No external DB needed; 10-entry LRU cap prevents RAM exhaustion |
| Cycle detection | `visited: set` in DFS | Prevents infinite recursion on circular coefficient graphs |
| Column names | Strip whitespace, **don't** lowercase | Preserves original casing for LLM variable matching |

---

## 7. Testing

The test suite at `backend/tests/test_backend.py` covers **118 assertions** across **13 test groups**:

| Group | What it covers |
|---|---|
| Health | Status code + body shape |
| Upload — Happy | `.xlsx`, `.csv`, whitespace stripping, dtype detection |
| Upload — Errors | 415 (bad type), 413 (too large), 422 (multiple primary) |
| Upload — Edge | Single-row, NaN, mixed types, 25 columns, 0 rows, Unicode |
| LRU Eviction | 12 uploads → oldest 2 evicted → newest accessible |
| Analyze — Happy | Response shape, driver ordering, R² range, trace fields |
| Analyze — Errors | 404 (unknown file_id), 422 (missing fields) |
| Analyze — Edge | Single-col, all-string, NaN, 2-row, constant, reproducibility, 20-feature |
| Simulate — Happy | Positive/negative/zero delta, impact structure |
| Simulate — Errors | 404, 409, 422 (invalid variable), missing fields |
| Simulate — Edge | Large delta, tiny delta, rounding |
| CORS | OPTIONS preflight |
| E2E | Full upload → analyze → simulate chain |

```bash
# Run tests
PYTHONPATH=. DEV_MODE=true python3 backend/tests/test_backend.py
```

---

## 8. Deployment (Render.com)

Config in `render.yaml` at project root:

```yaml
services:
  - type: web
    name: sota-statworks-api
    runtime: python
    rootDir: backend
    buildCommand: pip install -e .
    startCommand: uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

**Pre-demo checklist:**
1. Set `DEV_MODE=false` in Render env vars
2. Set `CORS_ORIGIN` to exact Vercel URL
3. Set at least `OPENAI_API_KEY_1`
4. Hit `GET /health` 5 min before demo to pre-warm
