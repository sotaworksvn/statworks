"""Student Profile Extractor — parses GPA, activity, and certificate Excel files.

Supports the multi-file upload format used for student scholarship analysis.
Returns a unified StudentProfile dict used by the analysis pipeline.
"""
from __future__ import annotations

import logging
import re
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def extract_student_profile_full(
    dfs: dict[str, "pd.DataFrame"],
    context_text: str = "",
) -> dict[str, Any]:
    """Extract a complete student profile from multiple uploaded dataframes.

    Parameters
    ----------
    dfs : dict[str, DataFrame]
        Mapping of file_name → parsed DataFrame (from multi-file upload).
    context_text : str
        Optional merged text extracted from all uploaded files.

    Returns
    -------
    dict with keys:
        name, dob, school, city, target_country, target_major, target_intake,
        gpa_10, gpa_4, semester_gpas (list of {semester, subject, score}),
        subject_averages (dict), strongest_subjects, weakest_subjects,
        toefl, ielts, sat, ap_courses (list),
        professional_certs (list), online_courses (list),
        extracurriculars (list), awards (list), soft_skill_certs (list),
        overall_tier, composite_score
    """
    profile: dict[str, Any] = {
        "name": "Học sinh",
        "dob": None,
        "school": None,
        "city": None,           # City/province extracted from school or HoatDong
        "target_country": None,
        "target_major": None,
        "target_intake": None,
        # Academic
        "gpa_10": None,
        "gpa_4": None,
        "semester_gpas": [],
        "subject_averages": {},
        "strongest_subjects": [],
        "weakest_subjects": [],
        # Language & standardized tests
        "toefl": None,
        "ielts": None,
        "sat": None,
        "ap_courses": [],
        # Enrichment
        "professional_certs": [],
        "online_courses": [],
        # Activities
        "extracurriculars": [],
        "awards": [],
        "soft_skill_certs": [],
    }

    for fname, df in dfs.items():
        fname_lower = fname.lower()
        if "gpa" in fname_lower or "diem" in fname_lower:
            _parse_gpa_file(df, profile)
        elif "hoatdong" in fname_lower or "hoatđộng" in fname_lower or "activity" in fname_lower:
            _parse_activity_file(df, profile)
        elif "chungchi" in fname_lower or "chứngchỉ" in fname_lower or "cert" in fname_lower:
            _parse_cert_file(df, profile)
        else:
            # Unknown file: try to parse as activity file (fallback)
            _try_parse_unknown(df, profile, fname)

    # Also try to extract from context text (merged OCR/text of all files)
    if context_text and profile.get("name") == "Học sinh":
        _extract_from_context(context_text, profile)

    # Extract name from HoatDong header if still missing
    if profile.get("name") == "Học sinh":
        _extract_name_from_headers(dfs, profile)

    # Derive city from school name
    _derive_city(profile)

    # Compute derived fields
    _compute_derived(profile)

    return profile


# ---------------------------------------------------------------------------
# Per-file parsers
# ---------------------------------------------------------------------------

def _parse_gpa_file(df: "pd.DataFrame", profile: dict) -> None:
    """Parse GPA / transcript Excel file."""
    all_text = _df_to_flat_text(df)

    # Extract name — check both label:value format and header line
    m = re.search(r"Họ và tên[:\s]*(.+)", all_text)
    if m:
        profile["name"] = m.group(1).strip().split("\t")[0].strip()

    m = re.search(r"Ngày sinh[:\s]*(.+)", all_text)
    if m:
        profile["dob"] = m.group(1).strip()

    m = re.search(r"Trường[:\s]*(.+)", all_text)
    if m:
        profile["school"] = m.group(1).strip()

    m = re.search(r"Mục tiêu du học[:\s]*(.+)", all_text)
    if m:
        raw = m.group(1).strip()
        profile["target_intent_raw"] = raw
        parts = [p.strip() for p in raw.split("-")]
        if len(parts) >= 1:
            profile["target_country"] = parts[0]
        if len(parts) >= 2:
            profile["target_major"] = parts[1]
        if len(parts) >= 3:
            profile["target_intake"] = parts[2]

    # Extract GPA average
    m = re.search(r"GPA Trung bình[:\s]*([\d.]+)", all_text)
    if m:
        try:
            profile["gpa_10"] = float(m.group(1))
            profile["gpa_4"] = round(_gpa_10_to_4(profile["gpa_10"]), 2)
        except ValueError:
            pass

    # Extract semester table  (subject | HK1 L10 | HK2 L10 | HK1 L11 | HK2 L11 | HK1 L12)
    semesters = ["HK1 Lớp 10", "HK2 Lớp 10", "HK1 Lớp 11", "HK2 Lớp 11", "HK1 Lớp 12"]
    semester_gpas = []
    subject_avgs: dict[str, list[float]] = {}

    # Find the header row
    header_row_idx = None
    for i, row in df.iterrows():
        vals = [str(v) for v in row.values]
        if any("Môn học" in v or "HK1" in v for v in vals):
            header_row_idx = i
            break

    if header_row_idx is not None:
        for i in range(int(header_row_idx) + 1, len(df)):
            row = df.iloc[i]
            vals = [str(v).strip() for v in row.values]
            non_empty = [v for v in vals if v and v not in ("nan", "NaT")]
            if len(non_empty) < 2:
                continue
            subject = non_empty[0]
            if not subject or "GPA" in subject or "Môn học" in subject:
                continue
            scores = []
            for v in non_empty[1:]:
                try:
                    scores.append(float(v))
                except ValueError:
                    pass

            for j, score in enumerate(scores[:5]):
                if j < len(semesters):
                    semester_gpas.append({"semester": semesters[j], "subject": subject, "score": score})
            if scores:
                subject_avgs[subject] = scores

    profile["semester_gpas"] = semester_gpas

    subj_avg = {s: round(sum(v) / len(v), 2) for s, v in subject_avgs.items() if v}
    profile["subject_averages"] = subj_avg

    if subj_avg:
        sorted_subj = sorted(subj_avg.items(), key=lambda x: x[1], reverse=True)
        profile["strongest_subjects"] = [s for s, _ in sorted_subj[:3]]
        profile["weakest_subjects"] = [s for s, _ in sorted_subj[-3:]]


def _parse_activity_file(df: "pd.DataFrame", profile: dict) -> None:
    """Parse extracurricular activities & awards file."""
    rows = _get_non_empty_rows(df)

    extracurriculars = []
    awards = []
    soft_skill_certs = []

    section = None
    in_data = False   # True after the column-header row of each section

    # Exact header row markers for each section (exact match to avoid false positives)
    EC_HEADER_MARKERS = {"Tên hoạt động", "Vai trò"}
    AWARD_HEADER_MARKERS = {"Giải thưởng", "Cấp độ"}
    SOFT_HEADER_MARKERS_EXACT = {"Chứng chỉ", "Tổ chức cấp"}   # exact col headers

    for r in rows:
        combined = " ".join(r)
        r_set = set(r)

        # Section detection
        if "HOẠT ĐỘNG NGOẠI KHÓA" in combined:
            section = "ec"
            in_data = False
            continue
        if "GIẢI THƯỞNG HỌC THUẬT" in combined:
            section = "award"
            in_data = False
            continue
        if "CHỨNG CHỈ KỸ NĂNG MỀM" in combined:
            section = "soft"
            in_data = False
            continue

        # Sub-section labels (e.g. "I. HOẠT ĐỘNG NGOẠI KHÓA")
        if re.match(r"^[IVX]+\.", r[0]) and len(r) == 1:
            continue

        # Detect column header row for each section (exact match)
        if section == "ec" and EC_HEADER_MARKERS.issubset(r_set):
            in_data = True
            continue
        if section == "award" and AWARD_HEADER_MARKERS.issubset(r_set):
            in_data = True
            continue
        if section == "soft" and SOFT_HEADER_MARKERS_EXACT.issubset(r_set):
            in_data = True
            continue

        if not in_data or len(r) < 2:
            continue

        if section == "ec" and len(r) >= 2:
            extracurriculars.append({
                "name": r[0],
                "role": r[1] if len(r) > 1 else "",
                "org": r[2] if len(r) > 2 else "",
                "period": r[3] if len(r) > 3 else "",
                "description": r[4] if len(r) > 4 else "",
            })
        elif section == "award" and len(r) >= 2:
            awards.append({
                "name": r[0],
                "level": r[1] if len(r) > 1 else "",
                "year": r[2] if len(r) > 2 else "",
                "description": r[3] if len(r) > 3 else "",
            })
        elif section == "soft" and len(r) >= 2:
            soft_skill_certs.append({
                "name": r[0],
                "org": r[1] if len(r) > 1 else "",
                "year": r[2] if len(r) > 2 else "",
                "description": r[3] if len(r) > 3 else "",
            })

    profile["extracurriculars"] = extracurriculars
    profile["awards"] = awards
    profile["soft_skill_certs"] = soft_skill_certs


def _parse_cert_file(df: "pd.DataFrame", profile: dict) -> None:
    """Parse academic certificates file."""
    rows = _get_non_empty_rows(df)

    ap_courses = []
    professional_certs = []
    online_courses = []

    section = None
    in_data = False

    for r in rows:
        vals = r
        combined_upper = " ".join(vals)
        combined_lower = combined_upper.lower()

        if "NGOẠI NGỮ" in combined_upper:
            section = "lang"
            in_data = False
            continue
        if "CHUYÊN MÔN" in combined_upper:
            section = "prof"
            in_data = False
            continue
        if "KHÓA HỌC ONLINE" in combined_upper:
            section = "online"
            in_data = False
            continue

        # Column header row detection (exact)
        if vals[0] in ("Chứng chỉ", "Khóa học", "Tên chứng chỉ"):
            in_data = True
            continue

        if not in_data or len(vals) < 2:
            continue

        cert_name = vals[0]
        cert_name_lc = cert_name.lower()

        if section == "lang":
            score_raw = vals[1] if len(vals) > 1 else ""
            try:
                score = float(score_raw)
            except ValueError:
                score = None

            if "toefl" in cert_name_lc:
                profile["toefl"] = score
            elif "ielts" in cert_name_lc:
                profile["ielts"] = score
            elif "sat" in cert_name_lc:
                profile["sat"] = score
            elif "ap " in cert_name_lc or cert_name.startswith("AP "):
                ap_courses.append({"name": cert_name, "score": score,
                                   "date": vals[2] if len(vals) > 2 else ""})

        elif section == "prof":
            professional_certs.append({
                "name": cert_name,
                "field": vals[1] if len(vals) > 1 else "",
                "date": vals[2] if len(vals) > 2 else "",
                "org": vals[3] if len(vals) > 3 else "",
            })

        elif section == "online":
            online_courses.append({
                "name": cert_name,
                "platform": vals[1] if len(vals) > 1 else "",
                "period": vals[2] if len(vals) > 2 else "",
                "has_cert": vals[3] if len(vals) > 3 else "",
            })

    if ap_courses:
        profile["ap_courses"] = ap_courses
    if professional_certs:
        profile["professional_certs"] = professional_certs
    if online_courses:
        profile["online_courses"] = online_courses


def _try_parse_unknown(df: "pd.DataFrame", profile: dict, fname: str) -> None:
    """Try to determine file type from content and parse accordingly."""
    all_text = _df_to_flat_text(df)
    if "HOẠT ĐỘNG NGOẠI KHÓA" in all_text or "GIẢI THƯỞNG" in all_text:
        _parse_activity_file(df, profile)
    elif "TOEFL" in all_text or "IELTS" in all_text or "SAT" in all_text:
        _parse_cert_file(df, profile)
    elif "Môn học" in all_text or "HK1" in all_text or "Họ và tên" in all_text:
        _parse_gpa_file(df, profile)


# ---------------------------------------------------------------------------
# Name / city helpers
# ---------------------------------------------------------------------------

def _extract_name_from_headers(dfs: dict[str, "pd.DataFrame"], profile: dict) -> None:
    """Extract student name from file header lines like 'XYZ - NGUYỄN VĂN AN'."""
    for fname, df in dfs.items():
        # Check the first few rows / column names for name patterns
        for i, row in df.iterrows():
            if i > 5:
                break
            for val in row.values:
                s = str(val).strip()
                # Pattern: "SOMETHING - HỌ TÊN" or just a long string with name
                m = re.search(r"-\s+([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯẠẢẤẦẨẪẬẮẰẲẴẶẸẺẼẾỀỂỄỆỈỊỌỎỐỒỔỖỘỚỜỞỠỢỤỦỨỪỬỮỰỲỴÝỶỸ ]{5,})\s*$", s)
                if m:
                    candidate = m.group(1).strip().title()
                    if 2 <= len(candidate.split()) <= 5:
                        profile["name"] = candidate
                        return


def _derive_city(profile: dict) -> None:
    """Derive city/province from school name."""
    school = profile.get("school") or ""
    # Map common school name patterns to cities
    city_patterns = [
        (r"Hà Nội|HN-Ams|Amsterdam|HNAMS", "Hà Nội"),
        (r"TP\.HCM|Hồ Chí Minh|HCM|Sài Gòn", "TP. Hồ Chí Minh"),
        (r"Đà Nẵng", "Đà Nẵng"),
        (r"Cần Thơ", "Cần Thơ"),
        (r"Hải Phòng", "Hải Phòng"),
        (r"Bình Dương", "Bình Dương"),
        (r"Đồng Nai", "Đồng Nai"),
        (r"Nghệ An", "Nghệ An"),
        (r"Huế|Thừa Thiên", "Huế"),
        (r"Quảng Nam", "Quảng Nam"),
    ]
    for pattern, city in city_patterns:
        if re.search(pattern, school, re.IGNORECASE):
            profile["city"] = city
            return
    # Fallback: extract from school name if contains "Chuyên + Location"
    m = re.search(r"Chuyên\s+(.+?)(?:\s*-|\s*$)", school)
    if m:
        profile["city"] = m.group(1).strip()


# ---------------------------------------------------------------------------
# Derived computation
# ---------------------------------------------------------------------------

def _compute_derived(profile: dict) -> None:
    """Compute composite score and overall tier."""
    score = 0.0
    weight_total = 0

    # GPA component (10-scale, max 10)
    gpa = profile.get("gpa_10")
    if gpa:
        score += (gpa / 10.0) * 50  # 50 points
        weight_total += 50

    # Standardized tests
    toefl = profile.get("toefl")
    ielts = profile.get("ielts")
    sat = profile.get("sat")

    test_score = 0.0
    test_n = 0
    if toefl:
        test_score += min(toefl / 120, 1.0)
        test_n += 1
    if ielts:
        test_score += min(ielts / 9.0, 1.0)
        test_n += 1
    if sat:
        test_score += min(sat / 1600, 1.0)
        test_n += 1
    if test_n:
        score += (test_score / test_n) * 30  # 30 points
        weight_total += 30

    # Extracurricular / achievement component
    ec_score = 0.0
    awards = profile.get("awards", [])
    ecs = profile.get("extracurriculars", [])
    ap_courses = profile.get("ap_courses", [])
    prof_certs = profile.get("professional_certs", [])

    if awards:
        for a in awards:
            level = a.get("level", "").lower()
            if "quốc tế" in level or "international" in level:
                ec_score += 3.5
            elif "quốc gia" in level or "national" in level:
                ec_score += 2.5
            elif "thành phố" in level or "city" in level:
                ec_score += 1.5
            else:
                ec_score += 0.5
    if ecs:
        for e in ecs:
            role = e.get("role", "").lower()
            if "trưởng" in role or "chủ" in role or "president" in role or "lead" in role:
                ec_score += 1.0
            else:
                ec_score += 0.5
    if ap_courses:
        for ap in ap_courses:
            try:
                if float(ap.get("score", 0)) >= 4:
                    ec_score += 0.5
            except (ValueError, TypeError):
                pass
    if prof_certs:
        ec_score += len(prof_certs) * 0.3

    ec_normalized = min(ec_score / 15.0, 1.0)
    score += ec_normalized * 20  # 20 points
    weight_total += 20

    if weight_total > 0:
        profile["composite_score"] = round(score, 1)
    else:
        profile["composite_score"] = None

    # Tier assignment
    composite = profile.get("composite_score") or 0
    if composite >= 90:
        tier = "Top 1%"
        tier_desc = "Extremely competitive — top global universities within reach"
    elif composite >= 80:
        tier = "Top 5%"
        tier_desc = "Highly competitive — strong scholarship prospects at selective universities"
    elif composite >= 70:
        tier = "Top 10%"
        tier_desc = "Competitive — good scholarship prospects at many universities"
    elif composite >= 60:
        tier = "Top 25%"
        tier_desc = "Above average — target universities likely accessible"
    else:
        tier = "Developing"
        tier_desc = "Focus on strengthening test scores and extracurricular achievements"

    profile["overall_tier"] = tier
    profile["tier_description"] = tier_desc

    # AP summary
    ap_5s = [a["name"] for a in profile.get("ap_courses", []) if a.get("score") == 5]
    if ap_5s:
        profile["ap_5_count"] = len(ap_5s)
        profile["ap_5_courses"] = ap_5s


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gpa_10_to_4(gpa_10: float) -> float:
    """Convert Vietnamese GPA (10-scale) to US GPA (4.0 scale)."""
    if gpa_10 >= 9.0:
        return 4.0
    elif gpa_10 >= 8.5:
        return 3.9
    elif gpa_10 >= 8.0:
        return 3.7
    elif gpa_10 >= 7.5:
        return 3.5
    elif gpa_10 >= 7.0:
        return 3.0
    elif gpa_10 >= 6.5:
        return 2.7
    elif gpa_10 >= 6.0:
        return 2.3
    else:
        return max(0.0, gpa_10 / 10 * 4)


def _df_to_flat_text(df: "pd.DataFrame") -> str:
    """Flatten a dataframe to searchable text (includes column names if data-like)."""
    lines = []
    # Include column names if they contain actual data (not default "Unnamed:")
    col_vals = [str(c).strip() for c in df.columns if not str(c).startswith("Unnamed:") and str(c).strip() not in ("nan", "")]
    if col_vals:
        lines.append("  ".join(col_vals))
    for _, row in df.iterrows():
        vals = [str(v).strip() for v in row.values if str(v).strip() not in ("nan", "NaT", "")]
        if vals:
            lines.append("  ".join(vals))
    return "\n".join(lines)


def _get_non_empty_rows(df: "pd.DataFrame") -> list[list[str]]:
    """Return list of non-empty row value lists."""
    result = []
    for _, row in df.iterrows():
        vals = [str(v).strip() for v in row.values if str(v).strip() not in ("nan", "NaT", "")]
        if vals:
            result.append(vals)
    return result


def _extract_from_context(text: str, profile: dict) -> None:
    """Best-effort extraction from merged text context."""
    m = re.search(r"(?:Họ và tên|Name)[:\s]*([^\n]+)", text)
    if m and profile.get("name") == "Học sinh":
        profile["name"] = m.group(1).strip()
