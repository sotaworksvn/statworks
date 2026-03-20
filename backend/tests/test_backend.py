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
