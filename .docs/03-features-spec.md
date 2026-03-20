# SOTA StatWorks — Feature Specifications

| Field            | Value                                |
|------------------|--------------------------------------|
| **Status**       | `draft`                              |
| **Team**         | Phú Nhuận Builder x SOTA Works       |
| **Project**      | SOTA StatWorks                       |
| **Created**      | 2026-03-20                           |
| **Last updated** | 2026-03-20                           |
| **PRD**          | `.docs/01-prd.md`                    |
| **System Design**| `.docs/02-system-design.md`          |

---

## Feature Index

| # | Feature | Endpoint(s) | Status |
|---|---|---|---|
| F-01 | [Data Ingestion](#f-01-data-ingestion) | `POST /upload` | `draft` |
| F-02 | [AI-Powered Driver Analysis](#f-02-ai-powered-driver-analysis) | `POST /analyze` | `draft` |
| F-03 | [Scenario Simulation](#f-03-scenario-simulation) | `POST /simulate` | `draft` |
| F-04 | [Frontend — Single-Screen Decision Interface](#f-04-frontend--single-screen-decision-interface) | — (Next.js) | `draft` |

---

---

# F-01: Data Ingestion

| Field | Value |
|---|---|
| **Status** | `draft` |
| **Endpoint** | `POST /upload` |
| **PRD reference** | PRD §5 Scope — Data ingestion |
| **System Design ref** | SD §4.4 Data Ingestion Layer, SD §6.2 Data Architecture |

---

## 1. Overview

The Data Ingestion feature is the entry point of every user session. It accepts one or more uploaded files, detects their type, parses them, and stores the result (a cleaned `DataFrame` plus optional text context) in the in-memory store under a generated `file_id`.

**Who it serves:** Every user who brings data to the system. Without this feature, no analysis or simulation is possible.

**Why it exists:** The system cannot operate on raw file bytes. Ingestion normalises heterogeneous input formats (structured data from Excel/CSV, unstructured context from Word/PowerPoint) into a unified representation that the AI Layer and statistical engines can consume.

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement |
|---|---|
| FR-01-01 | The endpoint `POST /upload` MUST accept multipart form-data with one or more files in a single request. |
| FR-01-02 | Supported primary data formats: `.xlsx`, `.csv`. These MUST be parsed into a `pandas.DataFrame`. |
| FR-01-03 | Supported context formats: `.docx`, `.pptx`. These MUST be parsed as plain text strings only (no formatting, no media). |
| FR-01-04 | Only one primary data file (`.xlsx` or `.csv`) is allowed per upload. If multiple primary files are submitted, return HTTP 422 with a descriptive error. |
| FR-01-05 | The endpoint MUST return a unique `file_id` (UUID v4) on success. |
| FR-01-06 | The parsed `DataFrame` and its column metadata MUST be stored in-memory under the returned `file_id`. |
| FR-01-07 | Extracted context text (from `.docx`/`.pptx`) MUST be stored alongside the `DataFrame` under the same `file_id`. |
| FR-01-08 | The endpoint MUST reject files exceeding 10 MB with HTTP 413. |
| FR-01-09 | The endpoint MUST reject unsupported file extensions with HTTP 415 and a clear message listing supported types. |
| FR-01-10 | Column names MUST be normalised (stripped of leading/trailing whitespace; no modification to casing). |
| FR-01-11 | Column types MUST be auto-detected. Numeric columns and non-numeric columns must be flagged in the metadata response. |
| FR-01-12 | The response MUST include: `file_id`, `columns` (list of `{name, dtype, is_numeric}`), `row_count`, `context_extracted` (bool). |

### 2.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01-01 | Upload and parse time MUST complete in < 3 seconds for files up to 10 MB. |
| NFR-01-02 | In-memory store MUST be capped at 10 active `file_id` entries. When the cap is reached, the oldest entry (insertion order) is evicted (LRU policy). |
| NFR-01-03 | The stored `DataFrame` MUST NOT be written to disk. All data is ephemeral per process lifetime. |
| NFR-01-04 | The in-memory store MUST be protected by a shared `asyncio.Lock` to prevent race conditions when multiple requests write concurrently. |

### 2.3 Acceptance Criteria

- Given a valid `.xlsx` file (< 10 MB), the response contains a `file_id`, the correct column list, and `row_count`.
- Given a `.docx` file alongside a `.csv`, the response contains `context_extracted: true` and the DataFrame is from the `.csv`.
- Given a 15 MB file, the response is HTTP 413.
- Given a `.pdf` file, the response is HTTP 415.
- Given two `.xlsx` files in one request, the response is HTTP 422.

---

## 3. Data Model

### Stored entry per `file_id`

```
{
  file_id: str (UUID v4),
  dataframe: pandas.DataFrame,
  columns: [{ name: str, dtype: str, is_numeric: bool }],
  row_count: int,
  context_text: str | None,       # concatenated text from .docx / .pptx
  coefficient_cache: dict | None  # populated after /analyze; used by /simulate
}
```

### HTTP Response — `POST /upload` (200 OK)

```json
{
  "file_id": "a3f2c1d4-...",
  "columns": [
    { "name": "Trust", "dtype": "float64", "is_numeric": true },
    { "name": "Retention", "dtype": "float64", "is_numeric": true }
  ],
  "row_count": 120,
  "context_extracted": true
}
```

---

## 4. Flows

### 4.1 Success — Structured + Context Files

```
Client  →  POST /upload (multipart: survey.xlsx + strategy.pptx)
           │
           ├─ Detect file types
           ├─ Parse survey.xlsx → DataFrame (pandas + openpyxl)
           ├─ Parse strategy.pptx → plain text (python-pptx)
           ├─ Normalise column names
           ├─ Detect column dtypes
           ├─ Generate file_id (UUID v4)
           ├─ Store { dataframe, context_text } in-memory
           └─ Return 200 { file_id, columns, row_count, context_extracted: true }
```

### 4.2 Failure — Oversized File

```
Client  →  POST /upload (multipart: huge.xlsx, 25 MB)
           │
           ├─ Check Content-Length / file size before parsing
           └─ Return 413 { "detail": "File exceeds the 10 MB limit." }
```

### 4.3 Failure — Unsupported Format

```
Client  →  POST /upload (multipart: report.pdf)
           │
           ├─ Detect extension: .pdf not in allowed set
           └─ Return 415 { "detail": "Unsupported file type. Allowed: .xlsx, .csv, .docx, .pptx" }
```

### 4.4 Failure — Multiple Primary Files

```
Client  →  POST /upload (multipart: data1.xlsx + data2.csv)
           │
           ├─ Count primary data files: 2 found
           └─ Return 422 { "detail": "Only one primary data file (.xlsx or .csv) is allowed per upload." }
```

---

## 5. Boundaries

**This feature owns:**
- File type detection and routing
- DataFrame parsing and column normalisation
- Context text extraction
- In-memory store writes (keyed by `file_id`)
- HTTP response shape for `/upload`

**This feature does NOT own:**
- Statistical computation (→ F-02)
- LLM calls (→ F-02)
- Simulation graph building (→ F-03)
- The `coefficient_cache` field is written by F-02 and read by F-03; F-01 only allocates the store entry

---

## 6. Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Primary parser | `pandas.read_excel` / `read_csv` with `openpyxl` engine | Zero extra setup; handles merged cells, multiple dtypes, and BOM-encoded CSVs |
| Context parser — Word | `python-docx`: iterate paragraphs and extract `.text` | Minimal; no formatting preservation needed |
| Context parser — PPT | `python-pptx`: iterate slides → shapes → text frames | Captures all text boxes without image or chart data |
| In-memory store type | `dict` with `asyncio.Lock` | Sufficient for single-session demo; avoids Redis setup cost |
| LRU eviction | `collections.OrderedDict` (10-entry cap) | Prevents unbounded RAM growth on Render's 512 MB free tier |
| `file_id` generation | `uuid.uuid4()` | Collision-free, no coordination needed |

---

## 7. Open Points

| # | Question | Options |
|---|---|---|
| OP-F01-1 | Should column name normalisation also lowercase all names? | (a) Strip whitespace only (preserve casing); (b) Also lowercase for case-insensitive matching downstream |
| OP-F01-2 | What is the maximum number of columns supported before the LLM prompt becomes too large? | (a) No limit (document risk); (b) Cap at 30 columns for the LLM prompt but keep full DataFrame |

---

---

# F-02: AI-Powered Driver Analysis

| Field | Value |
|---|---|
| **Status** | `draft` |
| **Endpoint** | `POST /analyze` |
| **PRD reference** | PRD §4 User Needs 1 & 4; PRD §5 Scope — Statistical engine, AI layer |
| **System Design ref** | SD §4.2 Request Lifecycle `/analyze`; SD §6.4 Error Handling |
| **LLM — Call 1** | OpenAI API · `gpt-5.4-mini` (JSON mode + function calling; 400K context; $0.75/1M input) |
| **LLM — Call 2** | OpenAI API · `gpt-5.4` (frontier model; up to 1.05M context; $2.50/1M input) |

---

## 1. Overview

Driver Analysis is the core intelligence feature of SOTA StatWorks. Given a `file_id` and a natural-language query, it orchestrates two LLM calls, one statistical computation, and a validation pipeline to produce a structured insight: ranked drivers, R², and a plain-English recommendation — all within 2 seconds.

**Who it serves:** All user segments — analysts, PMs, marketers, students — who need to understand what variable most strongly drives a target outcome.

**Why it exists:** This is the product's primary value proposition. It replaces the manual SPSS/SmartPLS workflow (upload → configure → run → interpret → write up) with a single natural-language question.

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement |
|---|---|
| FR-02-01 | `POST /analyze` MUST accept `{ file_id: string, query: string }`. |
| FR-02-02 | If `file_id` is unknown (not in store), return HTTP 404 with a descriptive message. |
| FR-02-03 | The system MUST invoke the AI Layer (LLM Call 1 — `gpt-5.4-mini` with JSON mode enabled) to extract: `intent`, `target`, `features[]` from the user query and the dataset's column list. |
| FR-02-04 | Allowed intent values: `driver_analysis`, `summary`, `comparison`. For v1, only `driver_analysis` triggers full computation; other intents return a `not_supported` response with a prompt suggestion. |
| FR-02-05 | All `features` returned by the LLM MUST be validated — stripped of any column name not present in the DataFrame. |
| FR-02-06 | If `target` is missing or not a valid column, the system MUST auto-detect: prefer the last column, then any column whose name contains "index", "score", or "rate". |
| FR-02-07 | If `features` is empty after validation, the system MUST fall back to: all numeric columns minus the `target` column. |
| FR-02-08 | The Decision Router MUST select the statistical engine by scoring: `score_pls = 0.4·L + 0.3·M + 0.3·C` and `score_reg = 0.6·O + 0.4·(1−C)`, where L = latent variable presence, M = multi-item indicator count, C = complexity, O = all-numeric observability. |
| FR-02-09 | The PLS engine MUST be selected only when `score_pls > score_reg`. Otherwise, OLS regression MUST be used. |
| FR-02-10 | The regression engine MUST compute: OLS coefficients (β), R², and p-values estimated via bootstrap (≤ 200 samples). |
| FR-02-11 | The PLS engine MUST compute: latent variable scores (mean of indicators), path coefficients, and bootstrap p-values. |
| FR-02-12 | The response MUST return at most 5 drivers, sorted by absolute coefficient descending. |
| FR-02-13 | The system MUST invoke the AI Layer (LLM Call 2 — `gpt-5.4`) to convert the statistical output into a plain-English summary and recommendation. |
| FR-02-14 | The response MUST include: `summary`, `drivers[{name, coef, p_value, significant}]`, `r2`, `recommendation`, `model_type` (`"regression"` or `"pls"`), `decision_trace` (object explaining why the engine was chosen). |
| FR-02-15 | The coefficient cache (`{ variable → [(target, coef)] }`) MUST be stored under `file_id` in the in-memory store after successful analysis, for use by F-03. |

### 2.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-02-01 | Total response time for `POST /analyze` MUST be < 2 seconds for datasets ≤ 500 rows and ≤ 10 features. |
| NFR-02-02 | LLM calls MUST be capped at 2 per request: Call 1 uses `gpt-5.4-mini`; Call 2 uses `gpt-5.4`. No additional calls are permitted. |
| NFR-02-03 | Total tokens per LLM call MUST NOT exceed 1000 (system prompt + user prompt combined). At `gpt-5.4-mini` pricing ($0.75/1M input, $4.50/1M output) this costs ~$0.00075/request; at `gpt-5.4` pricing ($2.50/1M input, $15.00/1M output) ~$0.0025/request. Total per analyze call: ~$0.003. |
| NFR-02-04 | Bootstrap sample count MUST be capped at 200 to respect the < 2s budget. |
| NFR-02-05 | Both LLM calls MUST use retry ×2 with 500ms backoff before triggering fallback logic. |
| NFR-02-06 | The system MUST return a valid response body in 100% of requests, even when all LLM calls fail. |

### 2.3 Acceptance Criteria

- Given `file_id` for a dataset with columns `[Trust, UX, Price, Retention]` and query `"What affects retention?"`, the response contains `target: "Retention"`, 3 drivers sorted by `|coef|`, a non-null `r2`, and a non-empty `recommendation`.
- Given a query with a column name not in the dataset, that column is absent from `drivers`.
- Given a deliberately malformed LLM output (mocked in test), the response still returns a valid `drivers` list (fallback activated).
- Given a dataset with < 30 rows and latent variable indicators, the engine falls back to regression and `decision_trace` reflects this.
- Given an unsupported intent (`"summary"`), the response contains `{ "not_supported": true, "suggestion": "..." }` with HTTP 200.

---

## 3. Data Model

### HTTP Request

```json
{ "file_id": "a3f2c1d4-...", "query": "What affects retention?" }
```

### HTTP Response — 200 OK

```json
{
  "summary": "Trust is the strongest driver of customer retention.",
  "drivers": [
    { "name": "Trust", "coef": 0.62, "p_value": 0.001, "significant": true },
    { "name": "UX",    "coef": 0.34, "p_value": 0.023, "significant": true },
    { "name": "Price", "coef": 0.08, "p_value": 0.412, "significant": false }
  ],
  "r2": 0.48,
  "recommendation": "Focus resources on improving Trust. It delivers the highest return on retention.",
  "model_type": "regression",
  "decision_trace": {
    "score_pls": 0.21,
    "score_reg": 0.54,
    "engine_selected": "regression",
    "reason": "Dataset has fully observable numeric columns; no latent variable indicators detected."
  }
}
```

### LLM Call 1 — Parsed Intent (internal)

```json
{ "intent": "driver_analysis", "target": "Retention", "features": ["Trust", "UX", "Price"] }
```

### LLM Call 2 — Insight Input (internal)

```json
{
  "drivers": [{ "name": "Trust", "coef": 0.62, "p_value": 0.001 }],
  "r2": 0.48,
  "model_type": "regression",
  "target": "Retention"
}
```

---

## 4. Flows

### 4.1 Success — Full Pipeline

```
Client  →  POST /analyze { file_id, query }
           │
           ├─ 1. Lookup file_id → retrieve DataFrame + context_text
           ├─ 2. LLM Call 1 — `gpt-5.4-mini` (OpenAI, JSON mode)
           │      System prompt: strict JSON schema
           │      User prompt: columns + context_text snippet + query
           │      → { intent, target, features }
           │
           ├─ 3. Validation Layer
           │      Strip invalid features → fallback if empty
           │      Auto-detect target if missing
           │
           ├─ 4. Decision Router
           │      Compute score_pls, score_reg → select engine
           │
           ├─ 5. Statistical Engine
           │      Run OLS or PLS → β, R², p-values (bootstrap ≤200)
           │      Build coefficient_cache → store under file_id
           │
           ├─ 6. LLM Call 2 — `gpt-5.4` (OpenAI)
           │      Input: drivers + r2 + model_type
           │      → { summary, recommendation }
           │
           └─ 7. Return 200 { summary, drivers, r2, recommendation, model_type, decision_trace }
```

### 4.2 Failure — LLM Call 1 Malformed Output (Fallback Chain Layer 1)

```
           ├─ LLM Call 1 → invalid JSON after 2 retries
           ├─ Fallback: features = all numeric columns minus inferred target
           ├─ Continue pipeline from step 4 (Decision Router)
           └─ Insight is template-generated (no LLM Call 2)
```

### 4.3 Failure — PLS Engine Fails (Fallback Chain Layer 2)

```
           ├─ Decision Router selects PLS
           ├─ PLS engine raises (singular matrix / insufficient rows)
           ├─ Fallback: run OLS regression instead
           ├─ decision_trace.reason updated to reflect fallback
           └─ Continue to LLM Call 2
```

### 4.4 Failure — All Computation Fails (Fallback Chain Layer 3)

```
           ├─ OLS also fails (zero-variance columns, all-NaN)
           └─ Return 200 {
                "summary": "Insufficient data for analysis.",
                "drivers": [],
                "r2": null,
                "recommendation": "Please check your dataset for missing or constant values.",
                "model_type": null,
                "decision_trace": { "engine_selected": null, "reason": "All engines failed." }
              }
```

### 4.5 Failure — Unknown file_id

```
Client  →  POST /analyze { file_id: "nonexistent", query: "..." }
           └─ Return 404 { "detail": "file_id not found. Please upload a dataset first." }
```

---

## 5. Boundaries

**This feature owns:**
- LLM call orchestration (calls 1 and 2)
- Validation and fallback logic
- Decision Router scoring
- OLS Regression Engine
- PLS Engine
- Coefficient cache write (stored in F-01's in-memory entry)
- Response shape for `/analyze`

**This feature does NOT own:**
- File parsing and DataFrame construction (→ F-01)
- Simulation propagation (→ F-03)
- UI rendering of insight (→ F-04)

---

## 6. Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| LLM structured output | OpenAI JSON mode (`response_format: { type: "json_object" }`) on `gpt-5.4-mini` | Native JSON mode is more reliable than prompt-only enforcement; `gpt-5.4-mini` additionally supports function calling for extra schema enforcement |
| LLM insight model | `gpt-5.4` for Call 2 | OpenAI's current frontier model (released March 5, 2026); up to 1.05M context window; 33% fewer factual errors vs. GPT-5.2; prose quality directly improves the recommendation judges read; ~$0.0025/request at ≤1k tokens — negligible against $400 budget |
| API client | `openai` Python SDK | Official SDK handles retries, timeouts, JSON mode, and function calling natively; simpler than raw `requests` |
| Bootstrap method | `numpy.random.choice` with replacement, ≤ 200 iterations | Fast; deterministic with seed; p-value accuracy sufficient for demo |
| OLS implementation | `β = (XᵀX)⁻¹Xᵀy` via `numpy.linalg.lstsq` | More numerically stable than explicit matrix inversion; no sklearn dependency |
| PLS latent variable | `LV = mean(indicator columns)` — simplified inner model | Full NIPALS/SmartPLS algorithm exceeds 30h build budget; simplified LV + path coef is defensible for demo |
| Significance threshold | `p_value < 0.05` → `significant: true` | Industry-standard threshold; clear to non-statistician users |
| Decision trace | Always included in response | Judges can inspect why the engine was chosen; adds transparency without UI clutter (collapsible in F-04) |

---

## 7. Open Points

| # | Question | Options |
|---|---|---|
| OP-F02-1 | How to handle queries that mix intents (e.g. "compare and find drivers")? | (a) Default to `driver_analysis`; (b) Return ambiguity response and ask user to clarify |
| OP-F02-2 | Should context_text from `.docx`/`.pptx` influence variable extraction or only insight generation? | (a) Send only to `gpt-5.4` Call 2 (insight); (b) Send to both calls — `gpt-5.4-mini`'s 400K context window can easily accommodate it |
| OP-F02-3 | Minimum dataset row count for PLS to be valid | (a) ≥ 30 rows hard gate → fallback to OLS; (b) Allow PLS with any size but warn |
| OP-F02-4 | API key rotation strategy | 4 OpenAI API keys available (one per account); which key rotation strategy to use if one hits rate limits | (a) Primary key + manual fallback; (b) Automatic round-robin across all 4 |

---

---

# F-03: Scenario Simulation

| Field | Value |
|---|---|
| **Status** | `draft` |
| **Endpoint** | `POST /simulate` |
| **PRD reference** | PRD §4 User Need 2; PRD §5 Scope — Scenario simulation |
| **System Design ref** | SD §4.3 Request Lifecycle `/simulate`; SD §6.3 Performance |

---

## 1. Overview

Scenario Simulation lets the user ask "what if?" — specifically: *"If I improve variable X by N%, how much does the target Y change?"* It operates on the coefficient cache produced by F-02, builds a directed causal graph, and propagates the delta through all downstream paths using DFS.

**Who it serves:** Product managers, business strategists, and analysts who need to quantify the return on a proposed intervention before committing resources.

**Why it exists:** Analysis alone shows *what matters*. Simulation shows *by how much* — turning insight into a decision. This is the feature that distinguishes SOTA StatWorks from a reporting tool.

---

## 2. Requirements

### 2.1 Functional Requirements

| ID | Requirement |
|---|---|
| FR-03-01 | `POST /simulate` MUST accept `{ file_id: string, variable: string, delta: float }` where `delta` is a fractional change (e.g. `0.20` = +20%). |
| FR-03-02 | If `file_id` is unknown, return HTTP 404. |
| FR-03-03 | If no `coefficient_cache` exists under `file_id` (i.e. `/analyze` has not been called first), return HTTP 409 with message: `"Run /analyze before /simulate."` |
| FR-03-04 | If `variable` is not a key in the coefficient cache, return HTTP 422 with a list of valid variable names. |
| FR-03-05 | The engine MUST build a directed graph from the coefficient cache: `{ source → [(target, coef)] }`. |
| FR-03-06 | The engine MUST compute delta propagation via DFS, accumulating direct and indirect impacts: 1-hop: `ΔY = β · ΔX`; multi-hop: `ΔZ = β_XZ·ΔX + β_YZ·(β_XY·ΔX)`. |
| FR-03-07 | The response MUST include `impacts`: a list of `{ variable, delta_pct }` for every node reachable from the input variable (excluding the input variable itself). |
| FR-03-08 | `delta_pct` values MUST be expressed as percentages (e.g. `12.4` = +12.4%), rounded to one decimal place. |
| FR-03-09 | The simulation MUST NOT re-run the statistical model. It consumes only the cached coefficients. |
| FR-03-10 | No LLM call is made during simulation. The response is purely deterministic. |

### 2.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-03-01 | Response time MUST be < 1 second for any graph with < 20 nodes. |
| NFR-03-02 | The DFS MUST detect and break cycles (prevent infinite propagation in circular graphs). |
| NFR-03-03 | Results MUST be deterministic — same input always produces same output. |

### 2.3 Acceptance Criteria

- Given `{ file_id, variable: "Trust", delta: 0.20 }` after a successful `/analyze`, the response contains `impacts: [{ variable: "Retention", delta_pct: 12.4 }]`.
- Given a `variable` not in the coefficient cache, the response is HTTP 422 with valid variable names listed.
- Given `/simulate` before `/analyze`, the response is HTTP 409.
- A cyclic graph (A→B→A) does not cause infinite recursion — the response terminates.

---

## 3. Data Model

### HTTP Request

```json
{ "file_id": "a3f2c1d4-...", "variable": "Trust", "delta": 0.20 }
```

### HTTP Response — 200 OK

```json
{
  "variable": "Trust",
  "delta": 0.20,
  "impacts": [
    { "variable": "Retention", "delta_pct": 12.4 },
    { "variable": "Satisfaction", "delta_pct": 7.1 }
  ]
}
```

### Internal Graph Representation

```python
# Built from coefficient_cache stored by F-02
graph = {
  "Trust": [("Retention", 0.62), ("Satisfaction", 0.35)],
  "UX":    [("Retention", 0.34)]
}
```

---

## 4. Flows

### 4.1 Success — Single-Hop Simulation

```
Client  →  POST /simulate { file_id, variable: "Trust", delta: 0.20 }
           │
           ├─ 1. Lookup file_id → retrieve coefficient_cache
           ├─ 2. Build directed graph from cache
           ├─ 3. DFS from "Trust"
           │      Retention: ΔRetention = 0.62 × 0.20 = 0.124 → 12.4%
           └─ 4. Return 200 { variable, delta, impacts }
```

### 4.2 Success — Multi-Hop Propagation

```
Graph: Trust → Retention (β=0.62), Trust → UX (β=0.45), UX → Retention (β=0.34)
Input: Trust +20%

DFS:
  Direct:   ΔRetention_direct  = 0.62 × 0.20 = 0.124
  Via UX:   ΔUX                = 0.45 × 0.20 = 0.090
            ΔRetention_via_ux  = 0.34 × 0.090 = 0.0306

  Total ΔRetention = 0.124 + 0.0306 = 0.1546 → 15.5%
  ΔUX = 9.0%

impacts: [{ variable: "Retention", delta_pct: 15.5 }, { variable: "UX", delta_pct: 9.0 }]
```

### 4.3 Failure — No Coefficient Cache

```
Client  →  POST /simulate { file_id, variable: "Trust", delta: 0.20 }
           ├─ Lookup file_id → coefficient_cache is None
           └─ Return 409 { "detail": "Run /analyze before /simulate." }
```

### 4.4 Failure — Invalid Variable

```
Client  →  POST /simulate { file_id, variable: "Revenue", delta: 0.10 }
           ├─ "Revenue" not in coefficient_cache keys
           └─ Return 422 {
                "detail": "Variable 'Revenue' not found.",
                "valid_variables": ["Trust", "UX", "Price"]
              }
```

---

## 5. Boundaries

**This feature owns:**
- Reading the `coefficient_cache` from in-memory store
- Directed graph construction
- DFS delta propagation
- HTTP response shape for `/simulate`

**This feature does NOT own:**
- Coefficient computation (→ F-02; cache is read-only here)
- LLM calls (none in this feature)
- Frontend slider UI (→ F-04)
- Re-running statistical models (explicitly prohibited)

---

## 6. Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Graph traversal | DFS with `visited` set | Prevents cycles; simple to implement; graph size < 20 nodes eliminates performance concern |
| Delta accumulation | Additive across paths | Consistent with linear model assumptions underlying OLS and simplified PLS |
| No LLM in simulation | Deterministic path only | Keeps response < 1s; removes reliability dependency on OpenRouter for what-if queries |
| Result rounding | 1 decimal place | Sufficient precision for business decision-making; avoids false precision |

---

## 7. Open Points

| # | Question | Options |
|---|---|---|
| OP-F03-1 | Should `/simulate` support multiple variable deltas simultaneously? | (a) Single variable only (v1); (b) Multi-variable object `{ Trust: 0.20, UX: 0.10 }` |
| OP-F03-2 | Should confidence intervals be shown on simulated delta? | (a) Point estimate only (faster, simpler); (b) Run bootstrap on simulation for 95% CI |
| OP-F03-3 | Should the endpoint accept negative `delta` values (e.g. -0.10 = −10%)? | (a) Yes — the math handles it naturally; (b) Validate ≥ 0 only (positive interventions) |

---

---

# F-04: Frontend — Single-Screen Decision Interface

| Field | Value |
|---|---|
| **Status** | `draft` |
| **Stack** | Next.js 14 (App Router) · TypeScript · TailwindCSS · Shadcn/UI · Recharts · Framer Motion |
| **Hosted on** | Vercel (hobby tier, deployed via `git push` to `main`) |
| **PRD reference** | PRD §4 User Needs 1–4; PRD §5 Scope — Frontend, UX |
| **System Design ref** | SD §4.5 Frontend Component Tree; SD §3 Tech Stack |

---

## 1. Overview

The frontend is a **single-screen decision interface** — not a dashboard and not a multi-page app. Every feature of the product is accessible from one view. The design principle: *if a user needs more than 10 seconds to understand the result, we failed.*

**Who it serves:** All SOTA StatWorks users — the interface is the product surface they interact with exclusively.

**Why it exists:** A great statistical engine produces zero value without an interface that translates its output into perceived intelligence. The frontend transforms numbers into decisions, and decisions into wow.

---

## 2. Requirements

### 2.1 Functional Requirements

#### Upload

| ID | Requirement |
|---|---|
| FR-04-01 | A drag-and-drop upload zone MUST be the first thing visible when no dataset is loaded. |
| FR-04-02 | The zone MUST accept `.xlsx`, `.csv`, `.docx`, `.pptx` via drag-and-drop or click-to-browse. |
| FR-04-03 | On successful upload, the dataset name and row count MUST appear in the `<Header>` badge. The upload zone MUST be replaced by the chat panel. |
| FR-04-04 | On upload failure, a visible error message MUST be displayed with the reason (e.g. "File too large", "Unsupported format"). |

#### Chat Panel

| ID | Requirement |
|---|---|
| FR-04-05 | A text input MUST be present at the bottom of the chat panel at all times after upload. |
| FR-04-06 | At least 3 pre-defined suggested prompts MUST appear above the input when the message list is empty, e.g.: *"What affects retention?"*, *"Which factor has the biggest impact?"*, *"What drives customer trust?"* |
| FR-04-07 | Clicking a suggested prompt MUST populate the input box and auto-submit. |
| FR-04-08 | While `/analyze` is loading, a skeleton/loading indicator MUST replace the insight panel with the message *"Analyzing relationships…"*. |
| FR-04-09 | After a response arrives, the user's query MUST appear as a message in the chat list above the input. |

#### Insight Panel

| ID | Requirement |
|---|---|
| FR-04-10 | The `<SummaryCard>` MUST display 1–2 lines of bold text summarising the top finding, e.g. *"Trust is the strongest driver of retention"*. |
| FR-04-11 | The `<DriverChart>` MUST render a horizontal bar chart, one bar per driver, sorted by absolute coefficient descending. Positive coefficients are green; negative coefficients are red. Hovering a bar MUST show `{ coef, p_value, significant }`. |
| FR-04-12 | The `<RecommendationCard>` MUST display the `recommendation` field from the API response in a visually distinct card (accent background). This card MUST be visible without scrolling. |
| FR-04-13 | The `<ModelInfoCollapse>` MUST be collapsed by default. Expanding it MUST reveal: `model_type`, `r2`, and `decision_trace.reason`. |
| FR-04-14 | The insight panel contents MUST animate in progressively: SummaryCard first → DriverChart (bars grow) → RecommendationCard (fade in). |

#### Simulation Bar

| ID | Requirement |
|---|---|
| FR-04-15 | The `<SimulationBar>` MUST be fixed at the bottom of the screen and MUST only appear after a successful `/analyze` response. |
| FR-04-16 | A `<VariableSelect>` dropdown MUST list all driver names from the last `/analyze` response. |
| FR-04-17 | A `<DeltaSlider>` MUST allow selection of `delta` from −50% to +50% in 5% increments. |
| FR-04-18 | A `<SimulateButton>` triggers `POST /simulate`. While loading, the button MUST show a spinner. |
| FR-04-19 | The simulation result MUST display as a `<ResultBadge>` with animated count-up, e.g. *"Retention +12.4%"*. If multiple impacts are returned, show all. |
| FR-04-20 | The displayed result MUST update whenever a new simulation completes (not accumulated — replace previous result). |

#### General

| ID | Requirement |
|---|---|
| FR-04-21 | If no dataset is loaded and the user interacts with the chat panel, a banner MUST appear: *"Upload a dataset to start."* |
| FR-04-22 | If `/analyze` returns an empty `drivers` list, the insight panel MUST display: *"We couldn't find strong drivers. Try a different question or check your dataset."* |
| FR-04-23 | A `<Header>` MUST always display the product name "SOTA StatWorks" and an upload/replace button when a dataset is active. |

### 2.2 Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-04-01 | Time from user submitting query to first visible insight content MUST be < 2 seconds (network + render). |
| NFR-04-02 | Time from clicking `<SimulateButton>` to animated result MUST be < 1 second. |
| NFR-04-03 | The layout MUST be optimised for 1280px+ viewport (desktop only for v1). No mobile breakpoints required. |
| NFR-04-04 | The page MUST achieve a Lighthouse Performance score ≥ 80 (no heavy unoptimised assets). |
| NFR-04-05 | All interactive elements (input, button, slider, dropdown) MUST have unique, descriptive HTML `id` attributes. |
| NFR-04-06 | All API communication MUST use the backend URL from an environment variable (`NEXT_PUBLIC_BACKEND_URL`). No hardcoded URLs. |
| NFR-04-07 | The frontend MUST display a clear error state (not a blank screen) when any API call fails with a non-2xx response. |

### 2.3 Acceptance Criteria

- Fresh load → upload zone visible, no other panels active.
- Upload `survey.xlsx` → Header shows `"survey.xlsx · 120 rows"`, chat panel appears with suggested prompts.
- Type *"What affects retention?"* → loading state appears → insight panel reveals SummaryCard, DriverChart, RecommendationCard in order with animation.
- Select `Trust` in SimulationBar, drag slider to +20%, click Simulate → badge shows `"Retention +12.4%"` within 1s.
- Simulate again with different variable → badge updates (does not accumulate).
- Simulate before uploading → banner: *"Upload a dataset to start."*

---

## 3. Data Model

### Zustand Global Store

```typescript
interface AppStore {
  fileId: string | null
  datasetName: string | null
  rowCount: number | null
  columns: Column[]          // { name, dtype, is_numeric }
  insight: InsightResult | null
  simulation: SimulationResult | null
  isAnalyzing: boolean
  isSimulating: boolean
  analyzeError: string | null
  simulateError: string | null
}
```

### InsightResult

```typescript
interface InsightResult {
  summary: string
  drivers: { name: string; coef: number; p_value: number; significant: boolean }[]
  r2: number | null
  recommendation: string
  model_type: "regression" | "pls" | null
  decision_trace: { score_pls: number; score_reg: number; engine_selected: string; reason: string }
}
```

### SimulationResult

```typescript
interface SimulationResult {
  variable: string
  delta: number
  impacts: { variable: string; delta_pct: number }[]
}
```

---

## 4. Flows

### 4.1 Upload Flow

```
User → drag file onto DropZone
       │
       ├─ react-dropzone validates extension (client-side)
       ├─ POST /upload (multipart)
       ├─ On success: store { fileId, datasetName, rowCount, columns } → Zustand
       │              replace DropZone with ChatPanel
       │              update Header badge
       └─ On error: show error toast with API detail message
```

### 4.2 Analyze Flow

```
User → type query + submit (or click suggested prompt)
       │
       ├─ Append user message to chat list
       ├─ Set isAnalyzing = true → show skeleton in InsightPanel
       ├─ POST /analyze { fileId, query } (React Query mutation)
       ├─ On success:
       │    Store InsightResult → Zustand
       │    Progressive reveal: SummaryCard → DriverChart → RecommendationCard
       │    Show SimulationBar
       │    Set isAnalyzing = false
       └─ On error: set analyzeError → show error message in chat area
```

### 4.3 Simulate Flow

```
User → select variable in VariableSelect
       adjust DeltaSlider → +20%
       click SimulateButton
       │
       ├─ Set isSimulating = true → show spinner on button
       ├─ POST /simulate { fileId, variable, delta } (React Query mutation)
       ├─ On success:
       │    Store SimulationResult → Zustand
       │    Animate ResultBadge: count-up from 0 to delta_pct
       │    Set isSimulating = false
       └─ On error: set simulateError → show error below SimulateButton
```

---

## 5. Boundaries

**This feature owns:**
- All Next.js pages and components (App Router, `app/` directory)
- Zustand store (`lib/store.ts`)
- API client functions (`lib/api.ts`) — thin wrappers around backend endpoints
- Animation and UX behaviour (Framer Motion, Recharts)
- Vercel deployment configuration (`vercel.json` if needed, otherwise zero-config)

**This feature does NOT own:**
- Backend API logic (→ F-01, F-02, F-03)
- Statistical computation
- LLM calls
- Data persistence

---

## 6. Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Framework | Next.js 14 App Router | Server components reduce initial JS bundle; App Router aligns with system design spec |
| Deployment | `git push` to `main` → Vercel auto-deploy | Zero-configuration; no Vercel CLI; constraint from PRD |
| State management | Zustand (global UI state) + React Query (server mutations) | Zustand is minimal and avoids Redux boilerplate; React Query manages loading/error lifecycle cleanly |
| Chart library | Recharts `<BarChart horizontal>` | Lightweight; React-native; sufficient for sorted driver bars |
| Animation | Framer Motion | `animate={{ width }}` on bar components; `useSpring` for count-up; `initial={{ opacity: 0 }}` for panel reveal |
| API base URL | `NEXT_PUBLIC_BACKEND_URL` env var | Required for Vercel → Render communication; avoids hardcoded Render URL |
| No Vercel serverless functions | All API calls go directly to Render backend | Zero server-side compute on Vercel; simpler CORS configuration |
| Error boundary | React `error.tsx` in App Router convention | Prevents blank screen on unexpected client errors |

---

## 7. Open Points

| # | Question | Options |
|---|---|---|
| OP-F04-1 | Should the chat panel persist message history within a session? | (a) Stateless — only last query shown (simpler); (b) Full history list scrollable |
| OP-F04-2 | Should negative simulation deltas (e.g. reducing Trust) be supported in the UI? | (a) Allow full −50% to +50% range; (b) Positive only (cleaner UX, avoids confusion) |
| OP-F04-3 | Should the DriverChart show confidence intervals as error bars? | (a) No — point estimate only (faster to implement); (b) Yes — show ± from bootstrap |
| OP-F04-4 | How to handle a second `/analyze` call after the first — replace insight or append? | (a) Replace (single insight view); (b) Show history of analyses in a panel |

---

## 8. Notes and References

| Item | Detail |
|---|---|
| Backend API base | `NEXT_PUBLIC_BACKEND_URL` (Render.com URL, set in Vercel project settings) |
| Upload endpoint | `POST /upload` — returns `file_id`, `columns`, `row_count` |
| Analyze endpoint | `POST /analyze` — accepts `file_id` + `query`, returns full insight |
| Simulate endpoint | `POST /simulate` — accepts `file_id`, `variable`, `delta`, returns `impacts` |
| Component tree | See System Design §4.5 |
| Animation WOW moments | Bar grow (DriverChart) · Count-up (ResultBadge) · Fade-in progressive reveal (InsightPanel) |
| PRD design rules | No jargon in default view · RecommendationCard always visible · No multi-page navigation |
