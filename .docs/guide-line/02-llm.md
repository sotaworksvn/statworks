# SOTA StatWorks — LLM Integration Guide

| Field            | Value                                            |
|------------------|--------------------------------------------------|
| **Last updated** | 2026-03-21                                       |
| **Phase**        | 2 — AI / LLM Integration                        |
| **Models**       | `gpt-5.4-mini` (Call 1) · `gpt-5.4` (Call 2)   |
| **Source**       | `backend/llm/` directory                         |

---

## 1. Overview

Phase 2 replaces the heuristic-only `/analyze` stub with a **two-call LLM pipeline**:

```
User Query
    │
    ▼
[LLM Call 1]  gpt-5.4-mini ── intent + variable extraction (JSON mode)
    │
    ▼
[Validation Layer]  strip hallucinated columns, auto-detect target/features
    │
    ▼
[Statistical Engine]  OLS regression or PLS (Decision Router selects)
    │
    ▼
[LLM Call 2]  gpt-5.4 ── business-language summary + recommendation
    │
    ▼
AnalyzeResponse (JSON)
```

At every step a **fallback layer** ensures the system never crashes and always returns a valid response.

---

## 2. Module Structure

```
backend/llm/
├── __init__.py     # Package init
├── client.py       # AsyncOpenAI client pool, key rotation, call_llm_with_retry()
├── parser.py       # LLM Call 1 — parse_user_intent() via gpt-5.4-mini
└── insight.py      # LLM Call 2 — generate_insight() via gpt-5.4
```

---

## 3. Environment Variables

Add to `backend/.env` (or Render dashboard for production):

```dotenv
# At least one key is required in production (DEV_MODE=false)
OPENAI_API_KEY_1=sk-...
OPENAI_API_KEY_2=sk-...   # optional — enables key rotation
OPENAI_API_KEY_3=sk-...   # optional
OPENAI_API_KEY_4=sk-...   # optional

# Set true for local dev without API keys (triggers fallback chain)
DEV_MODE=true
```

`config.py` reads `OPENAI_API_KEY_1` through `OPENAI_API_KEY_4` at import time. Keys are collected into `OPENAI_API_KEYS: list[str]`. If no keys are set and `DEV_MODE=false`, the app raises `ValueError` on startup.

---

## 4. `client.py` — OpenAI Client Management

### Client Pool

Up to 4 `AsyncOpenAI` instances are created at module load time, one per key:

```python
_clients: list[AsyncOpenAI] = []   # populated from OPENAI_API_KEYS
_active_index: int = 0             # round-robin cursor
```

### Key Rotation

On `RateLimitError`, `_rotate_client()` advances `_active_index` to the next key in the pool. The rotation is **round-robin** and **in-order** (key 1 → 2 → 3 → 4 → 1 → …).

### `call_llm_with_retry()`

```python
async def call_llm_with_retry(
    *,
    model: str,
    messages: list[dict[str, str]],
    response_format: dict[str, str] | None = None,
) -> dict[str, Any]: ...
```

**Retry policy** (per project rules):
- Max 3 total attempts (1 initial + 2 retries)
- 500ms backoff between attempts
- On `RateLimitError`: rotate to the next key, then retry immediately
- On `json.JSONDecodeError`: retry (markdown fences are auto-stripped before parsing)
- On any other `Exception`: retry
- After 3 failed attempts: raise `LLMFailureError`

**Markdown fence stripping** — if the model wraps its response in ` ```json...``` ` the client strips the fences before `json.loads()`.

### `LLMFailureError`

Custom exception raised when all retry attempts fail. Callers (`parser.py`, `insight.py`) catch it and activate their respective fallback layers.

---

## 5. `parser.py` — LLM Call 1: Intent Parsing

### Purpose

Translate the user's natural-language question into a structured intent dict that the Validation Layer and statistical engines can consume.

### Model

`gpt-5.4-mini` — fast, cost-efficient, forced to produce JSON via `response_format={"type": "json_object"}`.

### System Prompt

Enforces strict output schema. Key rules baked into the prompt:
- Output must match `{"intent": "...", "target": "...", "features": [...]}`
- `intent` must be one of: `driver_analysis`, `summary`, `comparison`
- **Only use column names from the dataset.** Do not hallucinate column names.
- If unsure about `features`, return `[]`. If unsure about `target`, return `null`.

### `parse_user_intent()`

```python
async def parse_user_intent(
    query: str,
    column_names: list[str],
    context_text: str | None = None,
) -> dict[str, Any]: ...
```

The user message is built as:
```
Dataset columns: Trust, UX, Price, Retention
Additional context: <first 500 chars of docx/pptx context, if any>
User question: What affects retention?
```

Context is **truncated to 500 characters** to respect the ≤1000-token budget.

### Layer 1 Fallback

On `LLMFailureError`, returns the safe default dict:
```python
{"intent": "driver_analysis", "target": None, "features": []}
```
The Validation Layer then auto-detects the target (last column heuristic) and auto-selects all numeric columns as features.

---

## 6. `insight.py` — LLM Call 2: Insight Generation

### Purpose

Convert statistical results (coefficients, R², driver rankings) into plain business language that a non-technical executive can understand and act on.

### Model

`gpt-5.4` — highest prose quality for user-facing text.

### System Prompt

Key constraint: **jargon ban**. The following words are explicitly forbidden:
`coefficient`, `p-value`, `regression`, `PLS`, `OLS`, `bootstrap`, `latent variable`, `SEM`, `beta`, `R-squared`

The model is instructed to write as if advising a CEO who has never taken a statistics class.

Output schema:
```json
{"summary": "string", "recommendation": "string"}
```

### `InsightText`

```python
class InsightText(BaseModel):
    summary: str
    recommendation: str
```

### `generate_insight()`

```python
async def generate_insight(
    drivers: list[dict],
    r2: float | None,
    target: str,
    model_type: str,
) -> InsightText: ...
```

The user prompt is built from driver data translated to natural language:
```
Target outcome: Retention
Key findings:
- Trust has a strong positive relationship with Retention (impact strength: 1.25)
- UX has a weak negative relationship with Retention (impact strength: 0.17)
The model explains 99% of the variation, which is a strong fit.
```

### Layer 4 Fallback (`_template_fallback`)

On `LLMFailureError`, returns deterministic template strings:
```
summary:        "<TopDriver> shows the strongest relationship with <target> (impact score X.XX)."
recommendation: "Focus resources on improving <TopDriver> to drive better <target> outcomes."
```
If there are no drivers at all, returns a generic "No strong drivers identified." message.

---

## 7. 4-Layer Fallback Chain

Per `04-rule.md §Common–Error Handling`, the `/analyze` endpoint **never crashes**. All four layers are implemented:

| Layer | Trigger | Fallback Action |
|-------|---------|-----------------|
| **1** | LLM Call 1 fails (`LLMFailureError`) | `parse_user_intent` returns `{intent: "driver_analysis", target: null, features: []}`. Validation Layer auto-detects target + features. |
| **2** | PLS engine raises `PLSFallbackError` | `analyze.py` catches it, updates `decision_trace.reason`, re-runs OLS. |
| **3** | OLS engine raises any `Exception` | Returns `AnalyzeResponse(drivers=[], r2=None, summary="Insufficient data...")`. |
| **4** | LLM Call 2 fails (`LLMFailureError`) | `generate_insight` returns `_template_fallback()` — deterministic template strings. |

---

## 8. Calling the `/analyze` Endpoint

```bash
# Step 1: Upload dataset
FILE_ID=$(curl -s -X POST http://localhost:8000/upload \
  -F "files=@data.csv;type=text/csv" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['file_id'])")

# Step 2: Analyze (triggers full 2-call LLM pipeline)
curl -s -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d "{\"file_id\": \"$FILE_ID\", \"query\": \"What affects customer retention?\"}" \
  | python3 -m json.tool
```

**Example response:**
```json
{
  "summary": "Customer trust is by far the main driver of retention...",
  "drivers": [
    {"name": "Trust",  "coef": 1.25, "p_value": 0.03, "significant": true},
    {"name": "UX",     "coef": 0.17, "p_value": 0.49, "significant": false}
  ],
  "r2": 0.997,
  "recommendation": "Make trust-building a priority across the customer journey...",
  "model_type": "regression",
  "decision_trace": {
    "score_pls": 0.49,
    "score_reg": 1.0,
    "engine_selected": "regression",
    "reason": "Dataset has fully observable numeric columns. Regression score (1.00) meets or exceeds PLS score (0.49)."
  }
}
```

**Key properties to verify:**
- `summary` and `recommendation` contain **no statistics jargon** (jargon-ban is enforced by system prompt)
- `drivers` are sorted by `abs(coef)` descending
- `decision_trace.engine_selected` is always populated unless all engines failed
- Response HTTP status is always `200` (errors are wrapped, not raised as crashes)

---

## 9. Diagnosing LLM Issues

### Check which models are available on your account

```python
# python3 /tmp/check_models.py
import asyncio, sys
sys.path.insert(0, '/path/to/sota-statworks-pro')
from backend.config import OPENAI_API_KEYS
from openai import AsyncOpenAI

async def check():
    client = AsyncOpenAI(api_key=OPENAI_API_KEYS[0])
    models = await client.models.list()
    gpt = sorted(m.id for m in models.data if 'gpt' in m.id)
    print('\n'.join(gpt))

asyncio.run(check())
```

### Test LLM calls in isolation

```bash
# From project root:
python3 - << 'EOF'
import asyncio, sys
sys.path.insert(0, '.')
from backend.llm.client import call_llm_with_retry

async def test():
    r = await call_llm_with_retry(
        model="gpt-5.4-mini",
        messages=[
            {"role": "system", "content": 'Return JSON: {"intent":"driver_analysis","target":"string","features":[]}'},
            {"role": "user",   "content": "Columns: Trust, UX, Price, Retention. Q: What affects retention?"},
        ],
        response_format={"type": "json_object"},
    )
    print(r)

asyncio.run(test())
EOF
```

### Common issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `summary` is a template string | Server running old code (pre-Phase 2) | Restart `uvicorn` |
| `LLMFailureError: No OpenAI API keys configured` | `OPENAI_API_KEY_*` not set | Add to `backend/.env` |
| `LLMFailureError` after 3 retries | Model not accessible on account | Run `check_models.py` and confirm model availability |
| JSON parse error in logs | Rare: model returned fenced JSON | Auto-handled by fence-stripping in `client.py` |

---

## 10. Cost & Performance Budget

Per `04-rule.md §Common–Performance`:

| Constraint | Value |
|------------|-------|
| Max LLM calls per `/analyze` request | 2 |
| Token budget per call | ≤ 1000 tokens |
| Context snippet truncation | 500 characters |
| `/analyze` target response time | < 2 seconds |
| Retry backoff | 500ms |
| Max retries | 2 (3 total attempts) |

The `analyze.py` handler logs a `WARNING` if elapsed time exceeds 1.8s, giving a 200ms buffer before the 2s budget.
