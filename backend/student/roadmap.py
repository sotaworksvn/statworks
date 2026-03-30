"""Roadmap Generator — personalized study roadmap from now until school deadlines.

Uses LLM with capability analysis + scholarship deadlines to generate
a month-by-month milestone timeline personalized for the student.
"""
from __future__ import annotations

import logging
from typing import Any
from datetime import date

logger = logging.getLogger(__name__)

# Today's date (from runtime)
TODAY = date(2026, 3, 22)


async def generate_roadmap(
    profile: dict[str, Any],
    capability: dict[str, Any],
    opportunities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Generate a personalized month-by-month scholarship roadmap.

    Returns
    -------
    list of milestone dicts:
        {
          "month": "Tháng 4/2026",
          "phase": "prep|test|apply|wait",
          "milestones": ["Milestone 1", "Milestone 2"],
          "priority": "high|medium|low",
          "notes": "..."
        }
    """
    from backend.llm.client import call_llm_with_retry

    # Build context
    name = profile.get("name", "học sinh")
    gpa_10 = profile.get("gpa_10", 8.88)
    gpa_4 = profile.get("gpa_4", 3.82)
    sat = profile.get("sat")
    toefl = profile.get("toefl")
    ielts = profile.get("ielts")
    tier = profile.get("overall_tier", "Top 5%")
    target = f"{profile.get('target_major', 'CS')} tại {profile.get('target_country', 'Mỹ')}"
    intake = profile.get("target_intake", "Fall 2026")
    gaps = capability.get("gaps", [])
    strengths_list = capability.get("strengths", [])

    # Get key deadlines from opportunities
    deadlines = []
    for opp in opportunities[:6]:
        dl = opp.get("deadline")
        school = opp.get("school_name", "")
        if dl and school:
            deadlines.append(f"{school}: {dl}")

    deadline_str = "\n".join(deadlines[:5]) if deadlines else "Hầu hết các trường: tháng 11-12/2025 (Early Decision) và tháng 1/2026 (Regular Decision)"

    prompt = f"""Tạo lộ trình học bổng cá nhân hoá từ tháng 4/2026 đến tháng 5/2026 cho học sinh sau.

Thông tin học sinh:
- Tên: {name}
- GPA: {gpa_10}/10 ({gpa_4}/4.0)
- SAT: {sat or 'Chưa có'}
- TOEFL: {toefl or 'Chưa có'}, IELTS: {ielts or 'Chưa có'}
- Mục tiêu: {target}, {intake}
- Profile tier: {tier}
- Điểm mạnh: {'; '.join(strengths_list[:3])}
- Điểm cần cải thiện: {'; '.join(gaps[:3])}

Deadline các trường đang nhắm tới:
{deadline_str}

Hôm nay là 22/03/2026. Intake là Fall 2026 nên các deadline quan trọng đã qua nhưng vẫn có thể:
1. Nộp supplemental scholarship applications muộn
2. Chuẩn bị cho Fall 2027 applications nếu cần
3. Cải thiện hồ sơ nếu đang wait-listed

Tạo lộ trình thực tế từ tháng 4 đến tháng 12/2026. Mỗi tháng là một mốc.

Return JSON: {{"roadmap": [
  {{
    "month": "Tháng 4/2026",
    "phase": "apply",  // prep | test | apply | wait | improve
    "milestones": ["Việc cụ thể 1", "Việc cụ thể 2"],
    "priority": "high",  // high | medium | low
    "notes": "Ghi chú cụ thể cho học sinh này"
  }}
]}}

Yêu cầu:
- Cực kỳ cụ thể và thực tế, không chung chung
- Cá nhân hoá dựa trên điểm mạnh và điểm yếu của học sinh này
- Nếu SAT chưa tốt, ưu tiên luyện SAT
- Đề cập đến các deadline cụ thể của các trường đã tìm được
- 6-9 mốc thời gian (tháng)"""

    try:
        raw = await call_llm_with_retry(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert US college admissions counselor specializing in "
                        "Vietnamese students. Generate highly personalized, actionable roadmaps. "
                        "Return ONLY valid JSON."
                    )
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        roadmap = raw.get("roadmap", [])
        if isinstance(roadmap, list) and roadmap:
            return roadmap

    except Exception as exc:
        logger.warning("Roadmap LLM failed: %s", exc)

    # Fallback: generate template roadmap
    return _template_roadmap(profile, gaps)


def _template_roadmap(profile: dict, gaps: list[str]) -> list[dict]:
    """Template fallback roadmap."""
    return [
        {
            "month": "Tháng 4/2026",
            "phase": "apply",
            "milestones": [
                "Kiểm tra trạng thái hồ sơ tại các trường đã apply",
                "Nộp scholarship supplemental applications nếu còn hạn",
                "Liên hệ thêm với 2-3 trường mới có deadline muộn",
            ],
            "priority": "high",
            "notes": "Tháng quan trọng — theo dõi sát kết quả từ các trường",
        },
        {
            "month": "Tháng 5-6/2026",
            "phase": "wait",
            "milestones": [
                "Nhận kết quả từ các trường",
                "So sánh các gói học bổng nhận được",
                "Tham dự các buổi accepted student day nếu được mời",
            ],
            "priority": "high",
            "notes": "Quyết định trường vào ngày 1/5 (National Decision Day)",
        },
        {
            "month": "Tháng 7-8/2026",
            "phase": "prep",
            "milestones": [
                "Hoàn thiện visa (F-1) và giấy tờ nhập học",
                "Tham gia nhóm du học sinh khóa 2030 của trường được chọn",
                "Nghiên cứu thêm học bổng ngoài trường (external scholarships)",
            ],
            "priority": "medium",
            "notes": "Chuẩn bị cho học kỳ đầu tiên tại Mỹ",
        },
    ]
