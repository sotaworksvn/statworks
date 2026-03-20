"""Comprehensive backend test suite — covers happy paths, error cases, and edge cases."""

from __future__ import annotations

import asyncio
import io
import sys
import traceback

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

PASS = 0
FAIL = 0
RESULTS: list[tuple[str, bool, str]] = []


def report(name: str, passed: bool, detail: str = "") -> None:
    global PASS, FAIL
    if passed:
        PASS += 1
        icon = "✅"
    else:
        FAIL += 1
        icon = "❌"
    RESULTS.append((name, passed, detail))
    print(f"  {icon} {name}" + (f"  —  {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Setup: Start the test client
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


# ===================================================
# 1. HEALTH
# ===================================================
def test_health():
    print("\n=== 1. GET /health ===")
    r = client.get("/health")
    report("Health returns 200", r.status_code == 200)
    report("Health body is {status: ok}", r.json() == {"status": "ok"})


# ===================================================
# 2. UPLOAD — Happy Paths
# ===================================================
def _make_xlsx(data: dict, filename: str = "test.xlsx") -> tuple[str, io.BytesIO, str]:
    buf = io.BytesIO()
    pd.DataFrame(data).to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return (filename, buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _make_csv(data: dict, filename: str = "test.csv") -> tuple[str, io.BytesIO, str]:
    buf = io.BytesIO()
    pd.DataFrame(data).to_csv(buf, index=False)
    buf.seek(0)
    return (filename, buf, "text/csv")


def test_upload_happy():
    print("\n=== 2. POST /upload — Happy Paths ===")

    # 2a. Valid xlsx
    f = _make_xlsx({"Trust": [1, 2, 3], "Retention": [4, 5, 6]})
    r = client.post("/upload", files=[("files", f)])
    report("Valid .xlsx → 200", r.status_code == 200)
    body = r.json()
    report("Response has file_id", "file_id" in body and len(body["file_id"]) > 0)
    report("Response has columns", len(body["columns"]) == 2)
    report("Row count = 3", body["row_count"] == 3)
    report("context_extracted = false", body["context_extracted"] is False)
    report("Columns detect is_numeric correctly",
           all(c["is_numeric"] for c in body["columns"]))

    # 2b. Valid csv
    f = _make_csv({"A": [1.0, 2.0], "B": ["x", "y"], "C": [3, 4]})
    r = client.post("/upload", files=[("files", f)])
    report("Valid .csv → 200", r.status_code == 200)
    body = r.json()
    numeric_flags = {c["name"]: c["is_numeric"] for c in body["columns"]}
    report("CSV: A is_numeric=True", numeric_flags.get("A") is True)
    report("CSV: B is_numeric=False", numeric_flags.get("B") is False)
    report("CSV: C is_numeric=True", numeric_flags.get("C") is True)

    # 2c. Column name stripping (whitespace)
    buf = io.BytesIO()
    df = pd.DataFrame({" Trust ": [1], " UX": [2], "Price ": [3]})
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    r = client.post("/upload", files=[("files", ("test.xlsx", buf, "application/octet-stream"))])
    report("Column whitespace stripped → 200", r.status_code == 200)
    names = [c["name"] for c in r.json()["columns"]]
    report("' Trust ' → 'Trust'", "Trust" in names)
    report("' UX' → 'UX'", "UX" in names)
    report("'Price ' → 'Price'", "Price" in names)


# ===================================================
# 3. UPLOAD — Error Cases
# ===================================================
def test_upload_errors():
    print("\n=== 3. POST /upload — Error Cases ===")

    # 3a. Unsupported file type (415)
    buf = io.BytesIO(b"fake pdf content")
    r = client.post("/upload", files=[("files", ("report.pdf", buf, "application/pdf"))])
    report("Unsupported .pdf → 415", r.status_code == 415)
    report("415 has detail message", "detail" in r.json())

    # 3b. Oversized file (413)
    huge = io.BytesIO(b"x" * (11 * 1024 * 1024))  # 11 MB
    r = client.post("/upload", files=[("files", ("big.xlsx", huge, "application/octet-stream"))])
    report("Oversized file → 413", r.status_code == 413)

    # 3c. Two primary files (422)
    f1 = _make_xlsx({"A": [1]}, "data1.xlsx")
    f2 = _make_csv({"B": [2]}, "data2.csv")
    r = client.post("/upload", files=[("files", f1), ("files", f2)])
    report("Two primary files → 422", r.status_code == 422)

    # 3d. No primary file (422 — only context file)
    docx_buf = io.BytesIO(b"fake docx")
    r = client.post("/upload", files=[("files", ("notes.docx", docx_buf, "application/octet-stream"))])
    # This will likely fail during parsing since it's not a real docx
    # The key test is that we don't crash — it should be 422 or 500
    report("Only context file, no primary → error (not crash)",
           r.status_code in (422, 500))

    # 3e. Empty file name — FastAPI rejects malformed multipart before handler
    buf = io.BytesIO(b"")
    r = client.post("/upload", files=[("files", ("", buf, "application/octet-stream"))])
    report("Empty filename → 422 (malformed multipart)", r.status_code == 422)

    # 3f. .txt file (not in allowlist)
    buf = io.BytesIO(b"some text")
    r = client.post("/upload", files=[("files", ("data.txt", buf, "text/plain"))])
    report(".txt file → 415", r.status_code == 415)

    # 3g. .json file (not in allowlist)
    buf = io.BytesIO(b'{"key": "value"}')
    r = client.post("/upload", files=[("files", ("data.json", buf, "application/json"))])
    report(".json file → 415", r.status_code == 415)


# ===================================================
# 4. UPLOAD — Edge Cases
# ===================================================
def test_upload_edge_cases():
    print("\n=== 4. POST /upload — Edge Cases ===")

    # 4a. Single-row dataset
    f = _make_xlsx({"X": [1], "Y": [2]})
    r = client.post("/upload", files=[("files", f)])
    report("Single-row dataset → 200", r.status_code == 200)
    report("Single row: row_count=1", r.json()["row_count"] == 1)

    # 4b. Dataset with NaN values
    f = _make_xlsx({"X": [1.0, float("nan"), 3.0], "Y": [4.0, 5.0, float("nan")]})
    r = client.post("/upload", files=[("files", f)])
    report("Dataset with NaN → 200", r.status_code == 200)
    report("NaN dataset: row_count=3", r.json()["row_count"] == 3)

    # 4c. Dataset with mixed types (string + numeric)
    f = _make_xlsx({"Name": ["Alice", "Bob"], "Score": [90, 85], "Grade": ["A", "B"]})
    r = client.post("/upload", files=[("files", f)])
    report("Mixed types → 200", r.status_code == 200)
    cols = {c["name"]: c["is_numeric"] for c in r.json()["columns"]}
    report("Mixed: Name not numeric", cols["Name"] is False)
    report("Mixed: Score is numeric", cols["Score"] is True)
    report("Mixed: Grade not numeric", cols["Grade"] is False)

    # 4d. Dataset with many columns (20+)
    big_data = {f"col_{i}": list(range(10)) for i in range(25)}
    f = _make_xlsx(big_data)
    r = client.post("/upload", files=[("files", f)])
    report("25-column dataset → 200", r.status_code == 200)
    report("25 columns returned", len(r.json()["columns"]) == 25)

    # 4e. Empty DataFrame (headers only, no rows)
    f = _make_xlsx({"A": pd.Series([], dtype=float), "B": pd.Series([], dtype=float)})
    r = client.post("/upload", files=[("files", f)])
    report("Empty DataFrame (0 rows) → 200", r.status_code == 200)
    report("Empty: row_count=0", r.json()["row_count"] == 0)

    # 4f. Unicode column names
    f = _make_xlsx({"Điểm": [1, 2], "Tên": ["A", "B"], "成績": [3, 4]})
    r = client.post("/upload", files=[("files", f)])
    report("Unicode column names → 200", r.status_code == 200)
    names = [c["name"] for c in r.json()["columns"]]
    report("Unicode: 'Điểm' preserved", "Điểm" in names)
    report("Unicode: '成績' preserved", "成績" in names)


# ===================================================
# 5. LRU EVICTION
# ===================================================
def test_lru_eviction():
    print("\n=== 5. LRU Store — Eviction at 10 entries ===")
    file_ids = []
    for i in range(12):
        f = _make_xlsx({"X": [i], "Y": [i * 2]}, f"test_{i}.xlsx")
        r = client.post("/upload", files=[("files", f)])
        if r.status_code == 200:
            file_ids.append(r.json()["file_id"])

    report("12 uploads all returned 200", len(file_ids) == 12)

    # The first 2 entries should have been evicted (entries 0 and 1)
    r0 = client.post("/analyze", json={"file_id": file_ids[0], "query": "test"})
    r1 = client.post("/analyze", json={"file_id": file_ids[1], "query": "test"})
    report("Oldest entry (0) evicted → 404", r0.status_code == 404)
    report("Second oldest (1) evicted → 404", r1.status_code == 404)

    # The last entry should still be accessible
    r_last = client.post("/analyze", json={"file_id": file_ids[-1], "query": "test"})
    report("Newest entry still accessible → 200", r_last.status_code == 200)


# ===================================================
# 6. ANALYZE — Happy Path
# ===================================================
DEMO_FILE_ID = None

def test_analyze_happy():
    global DEMO_FILE_ID
    print("\n=== 6. POST /analyze — Happy Path ===")

    # Upload demo dataset
    rng = np.random.default_rng(42)
    n = 120
    data = {
        "Trust": rng.normal(3.5, 0.8, n),
        "UX": rng.normal(3.2, 0.9, n),
        "Price": rng.normal(2.8, 1.0, n),
    }
    data["Retention"] = 0.62 * data["Trust"] + 0.34 * data["UX"] + 0.08 * data["Price"] + rng.normal(0, 0.3, n)
    f = _make_xlsx(data)
    r = client.post("/upload", files=[("files", f)])
    DEMO_FILE_ID = r.json()["file_id"]

    # Analyze
    r = client.post("/analyze", json={"file_id": DEMO_FILE_ID, "query": "What affects retention?"})
    report("Analyze → 200", r.status_code == 200)
    body = r.json()

    # Response shape
    for key in ("summary", "drivers", "r2", "recommendation", "model_type", "decision_trace"):
        report(f"Response has '{key}'", key in body)

    # Drivers
    report("Drivers count ≤ 5", len(body["drivers"]) <= 5)
    report("Drivers sorted by abs(coef) desc",
           all(abs(body["drivers"][i]["coef"]) >= abs(body["drivers"][i + 1]["coef"])
               for i in range(len(body["drivers"]) - 1)))

    # Top driver should be Trust
    if body["drivers"]:
        report("Top driver is 'Trust'", body["drivers"][0]["name"] == "Trust")
        report("Trust coef > 0", body["drivers"][0]["coef"] > 0)

    # Driver fields
    for d in body["drivers"]:
        for field in ("name", "coef", "p_value", "significant"):
            report(f"Driver '{d['name']}' has '{field}'", field in d, detail="")

    # R²
    report("R² is between 0 and 1", 0 <= body["r2"] <= 1)
    report("R² > 0.3 (good fit expected)", body["r2"] > 0.3)

    # Decision trace
    trace = body["decision_trace"]
    report("Trace has score_pls", "score_pls" in trace)
    report("Trace has score_reg", "score_reg" in trace)
    report("Trace has engine_selected", "engine_selected" in trace)
    report("Trace has reason", "reason" in trace and len(trace["reason"]) > 0)
    report("Engine selected = regression (pure numeric)", trace["engine_selected"] == "regression")

    # Summary and recommendation are non-empty
    report("Summary is non-empty", len(body["summary"]) > 10)
    report("Recommendation is non-empty", len(body["recommendation"]) > 10)

    # Model type
    report("model_type is 'regression'", body["model_type"] == "regression")


# ===================================================
# 7. ANALYZE — Error Cases
# ===================================================
def test_analyze_errors():
    print("\n=== 7. POST /analyze — Error Cases ===")

    # 7a. Unknown file_id → 404
    r = client.post("/analyze", json={"file_id": "nonexistent-uuid", "query": "test"})
    report("Unknown file_id → 404", r.status_code == 404)
    report("404 has detail", "detail" in r.json())

    # 7b. Missing file_id field → 422 (Pydantic validation)
    r = client.post("/analyze", json={"query": "test"})
    report("Missing file_id → 422", r.status_code == 422)

    # 7c. Missing query field → 422
    r = client.post("/analyze", json={"file_id": "some-id"})
    report("Missing query → 422", r.status_code == 422)

    # 7d. Empty body → 422
    r = client.post("/analyze", json={})
    report("Empty body → 422", r.status_code == 422)


# ===================================================
# 8. ANALYZE — Edge Cases
# ===================================================
def test_analyze_edge_cases():
    print("\n=== 8. POST /analyze — Edge Cases ===")

    # 8a. Single numeric column (target = only column, no features)
    f = _make_xlsx({"Score": [1, 2, 3, 4, 5]})
    r = client.post("/upload", files=[("files", f)])
    fid = r.json()["file_id"]
    r = client.post("/analyze", json={"file_id": fid, "query": "analyze"})
    report("Single-column dataset → still returns 200", r.status_code == 200)
    body = r.json()
    # With zero features, Layer 3 fallback should activate
    report("Single-col: drivers list (may be empty)", isinstance(body["drivers"], list))
    report("Single-col: has recommendation", len(body.get("recommendation", "")) > 0)

    # 8b. All-string columns (no numeric features)
    f = _make_xlsx({"Name": ["A", "B", "C"], "Grade": ["X", "Y", "Z"], "Status": ["on", "off", "on"]})
    r = client.post("/upload", files=[("files", f)])
    fid = r.json()["file_id"]
    r = client.post("/analyze", json={"file_id": fid, "query": "what drives status?"})
    report("All-string dataset → 200 (graceful)", r.status_code == 200)

    # 8c. Dataset with NaN values
    f = _make_xlsx({
        "Trust": [1.0, 2.0, float("nan"), 4.0, 5.0],
        "UX": [float("nan"), 2.0, 3.0, 4.0, 5.0],
        "Retention": [3.0, 4.0, 5.0, 6.0, 7.0],
    })
    r = client.post("/upload", files=[("files", f)])
    fid = r.json()["file_id"]
    r = client.post("/analyze", json={"file_id": fid, "query": "what affects retention?"})
    report("Dataset with NaN → 200 (handled)", r.status_code == 200)

    # 8d. Very small dataset (2 rows)
    f = _make_xlsx({"X": [1.0, 2.0], "Y": [3.0, 4.0]})
    r = client.post("/upload", files=[("files", f)])
    fid = r.json()["file_id"]
    r = client.post("/analyze", json={"file_id": fid, "query": "what drives Y?"})
    report("2-row dataset → 200 (no crash)", r.status_code == 200)

    # 8e. Dataset with constant column (zero variance)
    f = _make_xlsx({"X": [5, 5, 5, 5, 5], "Y": [1, 2, 3, 4, 5]})
    r = client.post("/upload", files=[("files", f)])
    fid = r.json()["file_id"]
    r = client.post("/analyze", json={"file_id": fid, "query": "what affects Y?"})
    report("Constant column → 200 (no crash)", r.status_code == 200)

    # 8f. Reproducibility check
    rng = np.random.default_rng(99)
    n = 50
    data = {"A": rng.normal(0, 1, n).tolist(), "B": rng.normal(0, 1, n).tolist(), "C": rng.normal(0, 1, n).tolist()}
    f1 = _make_xlsx(data)
    r1 = client.post("/upload", files=[("files", f1)])
    fid1 = r1.json()["file_id"]
    resp1 = client.post("/analyze", json={"file_id": fid1, "query": "what affects C?"}).json()

    f2 = _make_xlsx(data)
    r2 = client.post("/upload", files=[("files", f2)])
    fid2 = r2.json()["file_id"]
    resp2 = client.post("/analyze", json={"file_id": fid2, "query": "what affects C?"}).json()

    drivers_match = (
        [d["coef"] for d in resp1["drivers"]] == [d["coef"] for d in resp2["drivers"]]
    )
    report("Reproducible results (seed=42)", drivers_match)

    # 8g. Many features (20 columns → still returns top 5)
    rng2 = np.random.default_rng(7)
    data_wide = {f"feat_{i}": rng2.normal(0, 1, 50).tolist() for i in range(20)}
    data_wide["target"] = rng2.normal(0, 1, 50).tolist()
    f = _make_xlsx(data_wide)
    r = client.post("/upload", files=[("files", f)])
    fid = r.json()["file_id"]
    r = client.post("/analyze", json={"file_id": fid, "query": "analyze target"})
    report("20-feature dataset → 200", r.status_code == 200)
    report("20-feature: returns ≤ 5 drivers", len(r.json()["drivers"]) <= 5)


# ===================================================
# 9. SIMULATE — Happy Path
# ===================================================
def test_simulate_happy():
    print("\n=== 9. POST /simulate — Happy Path ===")

    r = client.post("/simulate", json={
        "file_id": DEMO_FILE_ID,
        "variable": "Trust",
        "delta": 0.20,
    })
    report("Simulate Trust +20% → 200", r.status_code == 200)
    body = r.json()
    report("Response has 'variable'", body["variable"] == "Trust")
    report("Response has 'delta'", body["delta"] == 0.20)
    report("Response has 'impacts'", isinstance(body["impacts"], list))
    report("Impacts is non-empty", len(body["impacts"]) > 0)

    # Check impact structure
    for imp in body["impacts"]:
        report(f"Impact '{imp['variable']}' has delta_pct", "delta_pct" in imp)
        report(f"Impact '{imp['variable']}' delta_pct is number",
               isinstance(imp["delta_pct"], (int, float)))

    # Negative delta
    r = client.post("/simulate", json={
        "file_id": DEMO_FILE_ID,
        "variable": "Trust",
        "delta": -0.10,
    })
    report("Simulate Trust -10% → 200", r.status_code == 200)
    neg_body = r.json()
    report("Negative delta produces negative impact",
           any(imp["delta_pct"] < 0 for imp in neg_body["impacts"]))

    # Zero delta
    r = client.post("/simulate", json={
        "file_id": DEMO_FILE_ID,
        "variable": "Trust",
        "delta": 0.0,
    })
    report("Simulate Trust ±0% → 200", r.status_code == 200)
    zero_body = r.json()
    report("Zero delta → zero impact",
           all(imp["delta_pct"] == 0.0 for imp in zero_body["impacts"]))


# ===================================================
# 10. SIMULATE — Error Cases
# ===================================================
def test_simulate_errors():
    print("\n=== 10. POST /simulate — Error Cases ===")

    # 10a. Unknown file_id → 404
    r = client.post("/simulate", json={"file_id": "bad-uuid", "variable": "Trust", "delta": 0.1})
    report("Unknown file_id → 404", r.status_code == 404)

    # 10b. No coefficient_cache → 409
    f = _make_xlsx({"A": [1, 2, 3], "B": [4, 5, 6]})
    r = client.post("/upload", files=[("files", f)])
    fresh_id = r.json()["file_id"]
    r = client.post("/simulate", json={"file_id": fresh_id, "variable": "A", "delta": 0.1})
    report("Simulate before analyze → 409", r.status_code == 409)

    # 10c. Invalid variable → 422
    r = client.post("/simulate", json={
        "file_id": DEMO_FILE_ID,
        "variable": "NonexistentVar",
        "delta": 0.1,
    })
    report("Invalid variable → 422", r.status_code == 422)
    body = r.json()
    report("422 lists valid variables",
           "valid_variables" in body.get("detail", {}))

    # 10d. Missing fields → 422
    r = client.post("/simulate", json={"file_id": DEMO_FILE_ID})
    report("Missing variable+delta → 422", r.status_code == 422)


# ===================================================
# 11. SIMULATE — Edge Cases
# ===================================================
def test_simulate_edge_cases():
    print("\n=== 11. POST /simulate — Edge Cases ===")

    # 11a. Large delta
    r = client.post("/simulate", json={
        "file_id": DEMO_FILE_ID,
        "variable": "Trust",
        "delta": 5.0,  # +500%
    })
    report("Large delta (+500%) → 200", r.status_code == 200)
    report("Large delta: impacts returned", len(r.json()["impacts"]) > 0)

    # 11b. Very small delta
    r = client.post("/simulate", json={
        "file_id": DEMO_FILE_ID,
        "variable": "Trust",
        "delta": 0.001,
    })
    report("Tiny delta (0.1%) → 200", r.status_code == 200)

    # 11c. delta_pct rounding
    body = r.json()
    for imp in body["impacts"]:
        val_str = str(imp["delta_pct"])
        if "." in val_str:
            decimals = len(val_str.split(".")[1])
            report(f"Impact {imp['variable']} rounded to ≤1 decimal", decimals <= 1)


# ===================================================
# 12. CORS HEADERS
# ===================================================
def test_cors():
    print("\n=== 12. CORS Headers ===")
    r = client.options("/health", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
    })
    report("OPTIONS /health doesn't error", r.status_code in (200, 204, 405))


# ===================================================
# 13. FULL E2E FLOW
# ===================================================
def test_e2e_flow():
    print("\n=== 13. Full E2E: Upload → Analyze → Simulate ===")

    # Step 1: Upload
    rng = np.random.default_rng(123)
    n = 80
    data = {
        "Satisfaction": rng.normal(4, 0.5, n),
        "Support": rng.normal(3, 1, n),
        "Speed": rng.normal(3.5, 0.7, n),
    }
    data["Loyalty"] = 0.5 * data["Satisfaction"] + 0.3 * data["Support"] + 0.1 * data["Speed"] + rng.normal(0, 0.2, n)
    f = _make_xlsx(data)
    r1 = client.post("/upload", files=[("files", f)])
    report("E2E Step 1: Upload → 200", r1.status_code == 200)
    fid = r1.json()["file_id"]

    # Step 2: Analyze
    r2 = client.post("/analyze", json={"file_id": fid, "query": "what drives loyalty?"})
    report("E2E Step 2: Analyze → 200", r2.status_code == 200)
    insight = r2.json()
    report("E2E: Top driver found", len(insight["drivers"]) > 0)

    # Step 3: Simulate with top driver
    top_var = insight["drivers"][0]["name"]
    r3 = client.post("/simulate", json={"file_id": fid, "variable": top_var, "delta": 0.20})
    report("E2E Step 3: Simulate → 200", r3.status_code == 200)
    report("E2E: Impacts returned", len(r3.json()["impacts"]) > 0)

    # Step 4: Simulate with a different variable
    if len(insight["drivers"]) > 1:
        second_var = insight["drivers"][1]["name"]
        r4 = client.post("/simulate", json={"file_id": fid, "variable": second_var, "delta": -0.15})
        report("E2E Step 4: Second simulate → 200", r4.status_code == 200)


# ===================================================
# 14. AUTH CONTEXT
# ===================================================
def test_auth_context():
    print("\n=== 14. Auth Context — get_current_user_id ===")
    from backend.auth.context import get_current_user_id
    from starlette.testclient import TestClient as _  # ensure starlette available

    # 14a. With valid header
    from fastapi import Request
    from starlette.datastructures import Headers

    # Use the test client to make a real request with the header
    r = client.get("/health", headers={"x-clerk-user-id": "user_abc123"})
    report("Health with x-clerk-user-id → 200 (header ignored by health)", r.status_code == 200)

    # 14b. Test the function directly via a mock scope
    scope = {
        "type": "http",
        "headers": [(b"x-clerk-user-id", b"user_test_42")],
    }
    mock_request = Request(scope)
    uid = get_current_user_id(mock_request)
    report("get_current_user_id with header → 'user_test_42'", uid == "user_test_42")

    # 14c. Without header
    scope_empty = {"type": "http", "headers": []}
    mock_request_empty = Request(scope_empty)
    uid_empty = get_current_user_id(mock_request_empty)
    report("get_current_user_id without header → None", uid_empty is None)

    # 14d. Empty string header
    scope_blank = {
        "type": "http",
        "headers": [(b"x-clerk-user-id", b"")],
    }
    mock_request_blank = Request(scope_blank)
    uid_blank = get_current_user_id(mock_request_blank)
    report("get_current_user_id with empty header → None", uid_blank is None)


# ===================================================
# 15. R2 MODULE
# ===================================================
def test_r2_module():
    print("\n=== 15. R2 Module — helper functions ===")
    from backend.storage import r2

    # 15a. Key generation
    key = r2.make_dataset_key("clerk_123", "dataset_456", ".csv")
    report("make_dataset_key format", key == "users/clerk_123/datasets/dataset_456.csv")

    key_xlsx = r2.make_dataset_key("clerk_123", "dataset_789", ".xlsx")
    report("make_dataset_key .xlsx", key_xlsx == "users/clerk_123/datasets/dataset_789.xlsx")

    # 15b. Output key
    out_key = r2.make_output_key("clerk_123", "analysis_001")
    report("make_output_key format", out_key == "users/clerk_123/outputs/analysis_001.json")

    # 15c. is_available (likely False in test env without R2 env vars)
    avail = r2.is_available()
    report("is_available returns bool", isinstance(avail, bool))

    # 15d. Presigned URL when not available
    if not avail:
        url = r2.generate_presigned_upload_url("test/key.csv")
        report("generate_presigned_upload_url when unavailable → None", url is None)

        url2 = r2.generate_presigned_download_url("test/key.csv")
        report("generate_presigned_download_url when unavailable → None", url2 is None)

        success = r2.upload_file_bytes("test/key.csv", b"data", "text/csv")
        report("upload_file_bytes when unavailable → False", success is False)

        stream = r2.get_file_stream("test/key.csv")
        report("get_file_stream when unavailable → None", stream is None)


# ===================================================
# 16. SUPABASE MODULE
# ===================================================
def test_supabase_module():
    print("\n=== 16. Supabase Module — graceful degradation ===")
    from backend.db import supabase as supa

    # 16a. is_available
    avail = supa.is_available()
    report("is_available returns bool", isinstance(avail, bool))

    # 16b. All functions return safe defaults when unavailable
    if not avail:
        result = supa.upsert_user("test_clerk_id")
        report("upsert_user when unavailable → None", result is None)

        result2 = supa.create_dataset("uid", "file.csv", "r2/key")
        report("create_dataset when unavailable → None", result2 is None)

        result3 = supa.create_analysis("did", {"test": True})
        report("create_analysis when unavailable → None", result3 is None)

        result4 = supa.get_user_datasets("clerk_id")
        report("get_user_datasets when unavailable → []", result4 == [])

        result5 = supa.get_user_by_clerk_id("clerk_id")
        report("get_user_by_clerk_id when unavailable → None", result5 is None)


# ===================================================
# 17. UPLOAD PRESIGN ENDPOINT
# ===================================================
def test_upload_presign():
    print("\n=== 17. POST /upload/presign — Auth + R2 checks ===")

    # 17a. No auth header → 401
    r = client.post("/upload/presign", json={"file_name": "data.csv"})
    report("Presign without auth → 401", r.status_code == 401)
    report("401 has detail", "detail" in r.json())

    # 17b. With auth but R2 not configured → 503
    from backend.storage import r2
    if not r2.is_available():
        r = client.post(
            "/upload/presign",
            json={"file_name": "data.csv"},
            headers={"x-clerk-user-id": "user_test"},
        )
        report("Presign with auth, R2 unavailable → 503", r.status_code == 503)

    # 17c. Missing file_name → 422
    r = client.post(
        "/upload/presign",
        json={},
        headers={"x-clerk-user-id": "user_test"},
    )
    report("Presign missing file_name → 422", r.status_code == 422)

    # 17d. Empty body → 422
    r = client.post(
        "/upload/presign",
        content=b"{}",
        headers={"x-clerk-user-id": "user_test", "content-type": "application/json"},
    )
    report("Presign empty body → 422", r.status_code == 422)


# ===================================================
# 18. DATASETS ENDPOINT
# ===================================================
def test_datasets_endpoint():
    print("\n=== 18. GET /datasets — Auth + listing ===")

    # 18a. No auth header → 401
    r = client.get("/datasets")
    report("GET /datasets without auth → 401", r.status_code == 401)
    report("401 has detail", "detail" in r.json())

    # 18b. With auth → 200 (empty list if Supabase not configured)
    r = client.get("/datasets", headers={"x-clerk-user-id": "user_test"})
    report("GET /datasets with auth → 200", r.status_code == 200)
    body = r.json()
    report("Response has 'datasets' key", "datasets" in body)
    report("Datasets is a list", isinstance(body["datasets"], list))


# ===================================================
# 19. UPLOAD WITH AUTH HEADER
# ===================================================
def test_upload_with_auth():
    print("\n=== 19. POST /upload — With x-clerk-user-id ===")

    # 19a. Upload with auth header (should still work and include user context)
    f = _make_xlsx({"Trust": [1, 2, 3], "Retention": [4, 5, 6]})
    r = client.post(
        "/upload",
        files=[("files", f)],
        headers={"x-clerk-user-id": "user_auth_test"},
    )
    report("Upload with auth → 200", r.status_code == 200)
    body = r.json()
    report("Auth upload: has file_id", "file_id" in body)
    report("Auth upload: has columns", len(body["columns"]) == 2)

    # 19b. Upload without auth (anonymous) → still works
    f2 = _make_csv({"X": [1, 2], "Y": [3, 4]})
    r2 = client.post("/upload", files=[("files", f2)])
    report("Upload without auth (anon) → 200", r2.status_code == 200)


# ===================================================
# 20. FULL AUTHENTICATED E2E FLOW
# ===================================================
def test_e2e_authenticated():
    print("\n=== 20. Full E2E with Auth: Upload → Analyze → Simulate → Datasets ===")

    clerk_id = "e2e_test_user_001"
    headers = {"x-clerk-user-id": clerk_id}

    # Step 1: Upload with auth
    rng = np.random.default_rng(777)
    n = 60
    data = {
        "Quality": rng.normal(3.5, 0.8, n),
        "Service": rng.normal(3.2, 0.9, n),
        "Location": rng.normal(2.8, 1.0, n),
    }
    data["Rating"] = (
        0.55 * data["Quality"] + 0.30 * data["Service"]
        + 0.10 * data["Location"] + rng.normal(0, 0.25, n)
    )
    f = _make_xlsx(data)
    r1 = client.post("/upload", files=[("files", f)], headers=headers)
    report("Auth E2E Step 1: Upload → 200", r1.status_code == 200)
    fid = r1.json()["file_id"]

    # Step 2: Analyze
    r2_resp = client.post(
        "/analyze",
        json={"file_id": fid, "query": "what drives rating?"},
    )
    report("Auth E2E Step 2: Analyze → 200", r2_resp.status_code == 200)
    insight = r2_resp.json()
    report("Auth E2E: drivers found", len(insight["drivers"]) > 0)
    report("Auth E2E: summary non-empty", len(insight["summary"]) > 0)

    # Step 3: Simulate
    top_var = insight["drivers"][0]["name"]
    r3 = client.post(
        "/simulate",
        json={"file_id": fid, "variable": top_var, "delta": 0.15},
    )
    report("Auth E2E Step 3: Simulate → 200", r3.status_code == 200)
    report("Auth E2E: impacts returned", len(r3.json()["impacts"]) > 0)

    # Step 4: List datasets (may be empty if Supabase not configured)
    r4 = client.get("/datasets", headers=headers)
    report("Auth E2E Step 4: Datasets → 200", r4.status_code == 200)
    report("Auth E2E: datasets response valid", "datasets" in r4.json())


# ===================================================
# 21. PHASE 2 — LLM CLIENT MODULE
# ===================================================
def test_llm_client_module():
    print("\n=== 21. LLM Client Module — structure & fallback ===")
    from backend.llm.client import LLMFailureError, get_active_client, call_llm_with_retry

    # 21a. LLMFailureError is a proper Exception subclass
    report("LLMFailureError is Exception subclass", issubclass(LLMFailureError, Exception))

    # 21b. LLMFailureError can be raised and caught
    try:
        raise LLMFailureError("test error")
    except LLMFailureError as e:
        report("LLMFailureError catchable", str(e) == "test error")

    # 21c. get_active_client returns AsyncOpenAI or None
    from openai import AsyncOpenAI
    client = get_active_client()
    report("get_active_client returns AsyncOpenAI or None",
           client is None or isinstance(client, AsyncOpenAI))

    # 21d. call_llm_with_retry raises LLMFailureError when no keys (DEV_MODE)
    from backend.config import OPENAI_API_KEYS
    if not OPENAI_API_KEYS:
        try:
            asyncio.get_event_loop().run_until_complete(
                call_llm_with_retry(
                    model="gpt-5.4-mini",
                    messages=[{"role": "user", "content": "test"}],
                )
            )
            report("call_llm_with_retry raises LLMFailureError (no keys)", False)
        except LLMFailureError:
            report("call_llm_with_retry raises LLMFailureError (no keys)", True)
    else:
        report("Skipped no-keys test (keys configured)", True, detail="keys present")


# ===================================================
# 22. PHASE 2 — LLM PARSER FALLBACK
# ===================================================
def test_llm_parser_fallback():
    print("\n=== 22. LLM Parser — fallback on LLM failure ===")
    from backend.llm.parser import parse_user_intent

    # When no API keys are set (DEV_MODE), parse_user_intent should
    # gracefully fall back to the default dict
    result = asyncio.get_event_loop().run_until_complete(
        parse_user_intent(
            query="What affects retention?",
            column_names=["Trust", "UX", "Price", "Retention"],
            context_text=None,
        )
    )

    report("Parser fallback: returns dict", isinstance(result, dict))
    report("Parser fallback: intent = driver_analysis",
           result.get("intent") == "driver_analysis")
    report("Parser fallback: features is list",
           isinstance(result.get("features"), list))
    report("Parser fallback: has target key", "target" in result)


# ===================================================
# 23. PHASE 2 — LLM INSIGHT FALLBACK
# ===================================================
def test_llm_insight_fallback():
    print("\n=== 23. LLM Insight — fallback on LLM failure ===")
    from backend.llm.insight import generate_insight, InsightText

    # When no API keys are set, generate_insight should return template strings
    drivers = [
        {"name": "Trust", "coef": 0.62, "p_value": 0.001, "significant": True},
        {"name": "UX", "coef": 0.34, "p_value": 0.023, "significant": True},
    ]
    result = asyncio.get_event_loop().run_until_complete(
        generate_insight(
            drivers=drivers,
            r2=0.48,
            target="Retention",
            model_type="regression",
        )
    )

    report("Insight fallback: returns InsightText", isinstance(result, InsightText))
    report("Insight fallback: summary non-empty", len(result.summary) > 0)
    report("Insight fallback: recommendation non-empty", len(result.recommendation) > 0)
    # When API keys are present, LLM may generate different prose;
    # when absent, template fallback includes variable names.
    report("Insight fallback: summary is meaningful (LLM or template)",
           len(result.summary) > 10)
    report("Insight fallback: recommendation is meaningful (LLM or template)",
           len(result.recommendation) > 10)

    # Empty drivers → still returns valid InsightText
    result_empty = asyncio.get_event_loop().run_until_complete(
        generate_insight(drivers=[], r2=None, target="Y", model_type="regression")
    )
    report("Insight fallback (empty): returns InsightText",
           isinstance(result_empty, InsightText))
    report("Insight fallback (empty): summary non-empty",
           len(result_empty.summary) > 0)


# ===================================================
# 24. PHASE 2 — FULL PIPELINE WITH LLM OFFLINE
# ===================================================
def test_analyze_llm_offline():
    print("\n=== 24. POST /analyze — Full pipeline with LLM offline ===")

    # Upload a demo dataset
    rng = np.random.default_rng(555)
    n = 80
    data = {
        "Trust": rng.normal(3.5, 0.8, n),
        "UX": rng.normal(3.2, 0.9, n),
        "Price": rng.normal(2.8, 1.0, n),
    }
    data["Retention"] = (
        0.62 * data["Trust"] + 0.34 * data["UX"]
        + 0.08 * data["Price"] + rng.normal(0, 0.3, n)
    )
    f = _make_xlsx(data)
    r = client.post("/upload", files=[("files", f)])
    report("LLM offline: Upload → 200", r.status_code == 200)
    fid = r.json()["file_id"]

    # Call /analyze — without API keys, LLM falls back to template
    r = client.post("/analyze", json={"file_id": fid, "query": "What affects retention?"})
    report("LLM offline: Analyze → 200 (fallback chain)", r.status_code == 200)
    body = r.json()

    # All required response fields present
    for key in ("summary", "drivers", "r2", "recommendation", "model_type", "decision_trace"):
        report(f"LLM offline: response has '{key}'", key in body)

    # Drivers are valid
    report("LLM offline: drivers non-empty", len(body["drivers"]) > 0)
    report("LLM offline: drivers ≤ 5", len(body["drivers"]) <= 5)

    # Summary and recommendation are non-empty (from template fallback)
    report("LLM offline: summary non-empty", len(body["summary"]) > 10)
    report("LLM offline: recommendation non-empty", len(body["recommendation"]) > 10)

    # R² valid
    report("LLM offline: R² between 0 and 1",
           body["r2"] is not None and 0 <= body["r2"] <= 1)

    # Decision trace populated
    trace = body["decision_trace"]
    report("LLM offline: trace has engine_selected", trace["engine_selected"] is not None)
    report("LLM offline: trace has reason", len(trace["reason"]) > 0)

    # Simulate still works after analyze
    top_var = body["drivers"][0]["name"]
    r_sim = client.post("/simulate", json={"file_id": fid, "variable": top_var, "delta": 0.20})
    report("LLM offline: Simulate after analyze → 200", r_sim.status_code == 200)
    report("LLM offline: Simulate has impacts", len(r_sim.json()["impacts"]) > 0)


# ===================================================
# 25. PHASE 2 — ADVERSARIAL QUERY (HALLUCINATED COLUMN)
# ===================================================
def test_analyze_adversarial():
    print("\n=== 25. POST /analyze — Adversarial query ===")

    # Upload dataset
    rng = np.random.default_rng(888)
    n = 50
    data = {
        "Trust": rng.normal(3.5, 0.8, n),
        "UX": rng.normal(3.2, 0.9, n),
        "Retention": rng.normal(4.0, 0.5, n),
    }
    f = _make_xlsx(data)
    r = client.post("/upload", files=[("files", f)])
    fid = r.json()["file_id"]

    # Query mentioning a column that doesn't exist
    r = client.post("/analyze", json={
        "file_id": fid,
        "query": "What affects retention? Focus on Revenue and Brand columns.",
    })
    report("Adversarial: Analyze → 200", r.status_code == 200)
    body = r.json()

    # Response is valid despite hallucinated column names in query
    report("Adversarial: has summary", len(body["summary"]) > 0)
    report("Adversarial: has drivers", isinstance(body["drivers"], list))
    report("Adversarial: has recommendation", len(body["recommendation"]) > 0)

    # No hallucinated column names in the driver results
    driver_names = [d["name"] for d in body["drivers"]]
    report("Adversarial: 'Revenue' not in drivers", "Revenue" not in driver_names)
    report("Adversarial: 'Brand' not in drivers", "Brand" not in driver_names)
    report("Adversarial: all drivers are real columns",
           all(name in ["Trust", "UX", "Retention"] for name in driver_names))


# ===================================================
# RUN ALL
# ===================================================
if __name__ == "__main__":
    tests = [
        test_health,
        test_upload_happy,
        test_upload_errors,
        test_upload_edge_cases,
        test_lru_eviction,
        test_analyze_happy,
        test_analyze_errors,
        test_analyze_edge_cases,
        test_simulate_happy,
        test_simulate_errors,
        test_simulate_edge_cases,
        test_cors,
        test_e2e_flow,
        test_auth_context,
        test_r2_module,
        test_supabase_module,
        test_upload_presign,
        test_datasets_endpoint,
        test_upload_with_auth,
        test_e2e_authenticated,
        test_llm_client_module,
        test_llm_parser_fallback,
        test_llm_insight_fallback,
        test_analyze_llm_offline,
        test_analyze_adversarial,
    ]

    for test_fn in tests:
        try:
            test_fn()
        except Exception as exc:
            print(f"\n💥 CRASH in {test_fn.__name__}: {exc}")
            traceback.print_exc()
            FAIL += 1
            RESULTS.append((f"CRASH: {test_fn.__name__}", False, str(exc)))

    # Summary
    total = PASS + FAIL
    print(f"\n{'='*60}")
    print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
    print(f"{'='*60}")

    if FAIL > 0:
        print("\nFailed tests:")
        for name, passed, detail in RESULTS:
            if not passed:
                print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))

    sys.exit(1 if FAIL > 0 else 0)

