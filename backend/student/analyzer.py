"""Student Capability Analyzer — SPSS-equivalent statistical analysis on student data.

Runs descriptive statistics and trend analysis across semester data to produce
an actionable capability insight report.
"""
from __future__ import annotations

import logging
import statistics
from typing import Any

logger = logging.getLogger(__name__)


def analyze_student_capability(profile: dict[str, Any]) -> dict[str, Any]:
    """Run SPSS-equivalent analysis on student profile data.

    Returns
    -------
    dict with keys:
        gpa_trend            — list of {semester, average_gpa} for line chart
        subject_stats        — list of {subject, mean, std, min, max, trend}
        strength_breakdown   — dict {category: score} for radar/bar chart
        key_insights         — list of plain-language insight strings
        capability_level     — "Xuất sắc" | "Giỏi" | "Khá" | "Trung bình"
        strongest_area       — str  e.g. "STEM" or "Ngôn ngữ"
        composite_score      — float 0–100
        strengths            — list[str]  (for display)
        gaps                 — list[str]  (for display)
    """
    result: dict[str, Any] = {}

    # ── 1. GPA Trend (per-semester average) ──
    sem_data: dict[str, list[float]] = {}
    for entry in profile.get("semester_gpas", []):
        sem = entry["semester"]
        score = entry["score"]
        sem_data.setdefault(sem, []).append(score)

    semesters_order = ["HK1 Lớp 10", "HK2 Lớp 10", "HK1 Lớp 11", "HK2 Lớp 11", "HK1 Lớp 12"]
    gpa_trend = []
    for sem in semesters_order:
        if sem in sem_data:
            avg = round(statistics.mean(sem_data[sem]), 2)
            gpa_trend.append({"semester": sem, "average_gpa": avg})
    result["gpa_trend"] = gpa_trend

    # ── 2. Per-subject descriptive stats ──
    subj_data: dict[str, list[float]] = {}
    for entry in profile.get("semester_gpas", []):
        subj_data.setdefault(entry["subject"], []).append(entry["score"])

    subject_stats = []
    for subj, scores in subj_data.items():
        if not scores:
            continue
        mean_v = round(statistics.mean(scores), 2)
        std_v = round(statistics.stdev(scores), 3) if len(scores) > 1 else 0.0
        # Trend: compare first half vs second half
        mid = len(scores) // 2
        if mid > 0 and len(scores) - mid > 0:
            first_half = statistics.mean(scores[:mid])
            second_half = statistics.mean(scores[mid:])
            trend = "↑" if second_half > first_half + 0.05 else ("↓" if second_half < first_half - 0.05 else "→")
        else:
            trend = "→"

        subject_stats.append({
            "subject": subj,
            "mean": mean_v,
            "std": std_v,
            "min": round(min(scores), 2),
            "max": round(max(scores), 2),
            "trend": trend,
            "n_semesters": len(scores),
        })

    # Sort by mean descending
    subject_stats.sort(key=lambda x: x["mean"], reverse=True)
    result["subject_stats"] = subject_stats

    # ── 3. Strength Breakdown (for bar chart) ──
    strength_breakdown = {}

    # Academic STEM
    stem_subjs = ["Toán", "Vật lý", "Hóa học", "Sinh học", "Tin học"]
    stem_scores = [s["mean"] for s in subject_stats if s["subject"] in stem_subjs]
    if stem_scores:
        strength_breakdown["STEM"] = round(statistics.mean(stem_scores), 2)

    # Language
    lang_subjs = ["Tiếng Anh", "Ngữ văn"]
    lang_scores = [s["mean"] for s in subject_stats if s["subject"] in lang_subjs]
    if lang_scores:
        strength_breakdown["Ngôn ngữ"] = round(statistics.mean(lang_scores), 2)

    # Standardized tests (normalized to 10)
    test_components = []
    if profile.get("ielts"):
        test_components.append(profile["ielts"] / 9 * 10)
    if profile.get("toefl"):
        test_components.append(profile["toefl"] / 120 * 10)
    if profile.get("sat"):
        test_components.append(profile["sat"] / 1600 * 10)
    if test_components:
        strength_breakdown["Chứng chỉ Quốc tế"] = round(statistics.mean(test_components), 2)

    # Extracurricular
    ec_score = _compute_ec_score(profile)
    strength_breakdown["Hoạt động"] = round(min(ec_score * 10 / 15, 10), 2)

    # Research
    awards = profile.get("awards", [])
    intl_awards = [a for a in awards if "quốc tế" in a.get("level", "").lower()]
    natl_awards = [a for a in awards if "quốc gia" in a.get("level", "").lower()]
    research_score = min(len(intl_awards) * 3 + len(natl_awards) * 2 + len(awards) * 0.5, 10)
    strength_breakdown["Nghiên cứu & Giải thưởng"] = round(research_score, 2)

    result["strength_breakdown"] = strength_breakdown

    # ── 4. Key Insights ──
    insights = []
    gpa_10 = profile.get("gpa_10")
    if gpa_10:
        if gpa_10 >= 9.0:
            insights.append(f"GPA xuất sắc {gpa_10}/10 — nằm trong nhóm top 5% học sinh toàn quốc")
        elif gpa_10 >= 8.5:
            insights.append(f"GPA giỏi {gpa_10}/10 — đáp ứng yêu cầu của hầu hết học bổng quốc tế")
        else:
            insights.append(f"GPA {gpa_10}/10 — cần cải thiện để tăng khả năng nhận học bổng")

    if profile.get("sat"):
        sat = profile["sat"]
        if sat >= 1500:
            insights.append(f"SAT {sat} — thuộc nhóm top 4% toàn cầu, rất cạnh tranh cho các trường Ivy League")
        elif sat >= 1400:
            insights.append(f"SAT {sat} — đủ điều kiện cho hầu hết các trường đại học hàng đầu")

    if profile.get("toefl") and profile["toefl"] >= 110:
        insights.append(f"TOEFL {profile['toefl']} — vượt ngưỡng yêu cầu của MIT, Stanford, Harvard")

    if profile.get("ielts") and profile["ielts"] >= 7.5:
        insights.append(f"IELTS {profile['ielts']} — đủ điều kiện cho mọi trường đại học hàng đầu thế giới")

    intl_aw = [a for a in awards if "quốc tế" in a.get("level", "").lower()]
    if intl_aw:
        insights.append(f"Giải thưởng quốc tế: {', '.join(a['name'] for a in intl_aw[:2])} — tăng đáng kể hồ sơ học bổng")

    natl_aw = [a for a in awards if "quốc gia" in a.get("level", "").lower()]
    if natl_aw:
        insights.append(f"Giải quốc gia: {', '.join(a['name'] for a in natl_aw[:2])} — tương đương chuẩn học bổng nhiều trường top-25 Mỹ")

    if subject_stats:
        top_subj = subject_stats[0]
        insights.append(f"Môn học nổi bật nhất: {top_subj['subject']} (TB {top_subj['mean']}/10) — phù hợp định hướng {profile.get('target_major', 'STEM')}")

    result["key_insights"] = insights

    # ── 5. Capability level ──
    gpa_raw = profile.get("gpa_10") or 0
    cap_level = (
        "Xuất sắc" if gpa_raw >= 9.0 else
        "Giỏi" if gpa_raw >= 8.0 else
        "Khá" if gpa_raw >= 6.5 else
        "Trung bình"
    )
    result["capability_level"] = cap_level

    # ── 6. Strongest area ──
    if strength_breakdown:
        strongest_area = max(strength_breakdown, key=lambda k: strength_breakdown[k])
        result["strongest_area"] = strongest_area
    else:
        result["strongest_area"] = "STEM"

    # ── 7. Composite ──
    result["composite_score"] = profile.get("composite_score")

    # ── 8. Strengths & Gaps ──
    strengths = []
    gaps = []

    if gpa_raw >= 8.5:
        strengths.append(f"GPA cao ({gpa_raw}/10) — đáp ứng yêu cầu hầu hết học bổng quốc tế")
    else:
        gaps.append("GPA cần cải thiện — mục tiêu: 8.5/10 trở lên")

    if profile.get("sat") and profile["sat"] >= 1500:
        strengths.append(f"SAT {profile['sat']} — top 4% toàn cầu")
    elif profile.get("sat"):
        gaps.append(f"SAT {profile['sat']} — cải thiện lên 1550+ để tăng cạnh tranh")

    if profile.get("toefl") and profile["toefl"] >= 110:
        strengths.append(f"TOEFL {profile['toefl']} — xuất sắc")
    elif profile.get("ielts") and profile["ielts"] >= 7.5:
        strengths.append(f"IELTS {profile['ielts']} — xuất sắc")
    else:
        gaps.append("Cần chứng chỉ tiếng Anh mạnh hơn (IELTS 8.0+ hoặc TOEFL 110+)")

    if intl_aw:
        strengths.append(f"{len(intl_aw)} giải thưởng quốc tế — cạnh tranh cao")
    if natl_aw:
        strengths.append(f"{len(natl_aw)} giải thưởng quốc gia")

    ap_5s = [a for a in profile.get("ap_courses", []) if a.get("score") == 5]
    if ap_5s:
        strengths.append(f"{len(ap_5s)} AP điểm 5 — chứng minh năng lực học thuật")

    if not intl_aw and not natl_aw:
        gaps.append("Cần giải thưởng học thuật cấp quốc gia/quốc tế để tăng cạnh tranh")

    result["strengths"] = strengths
    result["gaps"] = gaps

    return result


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _compute_ec_score(profile: dict) -> float:
    """Compute raw extracurricular score (unnormalized)."""
    score = 0.0
    for a in profile.get("awards", []):
        level = a.get("level", "").lower()
        if "quốc tế" in level:
            score += 3.5
        elif "quốc gia" in level:
            score += 2.5
        elif "thành phố" in level:
            score += 1.5
        else:
            score += 0.5
    for e in profile.get("extracurriculars", []):
        role = e.get("role", "").lower()
        if any(kw in role for kw in ("trưởng", "chủ", "president", "lead")):
            score += 1.0
        else:
            score += 0.5
    return score
