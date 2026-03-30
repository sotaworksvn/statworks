<div align="center">

<img src="frontend/public/logo.png" alt="SOTA StatWorks" width="400" />

### From Student Data to Scholarship Opportunities, Instantly

**AI-powered student profile analysis engine** that turns raw academic data into scholarship opportunities, capability insights, and personalized roadmaps — without any statistical expertise.

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)
[![LotusHacks 2026](https://img.shields.io/badge/LotusHacks-2026-orange.svg)](https://lotushack.org)
[![Track: EdTech by ETEST](https://img.shields.io/badge/Track-EdTech%20by%20ETEST-green.svg)]()

---

<img src="frontend/public/phunhuanbuilder.png" alt="Phú Nhuận Builder" height="70" />&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;<img src="frontend/public/sotaworks.png" alt="SOTA Works" height="70" />

**Phú Nhuận Builder × SOTA Works**

</div>

---

## 🧩 The Problem

Students in Vietnam have strong academic records but miss out on scholarships because:

- **No unified view** of their own profile — GPA, certificates, activities scattered across documents
- **No awareness** of matching scholarship opportunities abroad
- **No personalized roadmap** — generic advice that doesn't account for their actual strengths and gaps
- **Existing tools** like SPSS or SmartPLS require statistical expertise most high-schoolers don't have

**The gap:** A student with a 8.88 GPA, TOEFL 112, and 2 national-level awards doesn't know they're in the **Top 1%** — and doesn't know which universities would actively recruit them.

## 💡 The Solution

**SOTA StatWorks — EdTech Track** — one screen, three Excel files, one complete scholarship roadmap.

Upload GPA, activity, and certificate files, ask in natural language, and get:

1. **Capability Analysis** — SPSS-equivalent statistical breakdown: GPA trend, subject-level descriptive stats, strength breakdown by area
2. **Scholarship Opportunities** — AI web-searched opportunities matched to the student's exact profile tier, with match scores and deadlines
3. **Personalized Roadmap** — Month-by-month action plan from now to application deadline
4. **Simulate Bar** — Adjust GPA, test scores, or award level to see predicted impact on match score for any target university

No statistical knowledge required. No manual configuration. No jargon.

## ✨ What Makes Us Different

| Feature | Tư vấn tay | ChatGPT | **SOTA StatWorks EdTech** |
|---------|-----------|---------|--------------------------|
| Real statistical analysis of transcript | ❌ | ❌ | ✅ |
| Web-searched, up-to-date scholarships | ❌ | ~ | ✅ |
| Match score per university | ❌ | ❌ | ✅ |
| Personalized month-by-month roadmap | ❌ | ~ | ✅ |
| What-if simulation | ❌ | ❌ | ✅ |
| Multi-file upload (GPA + Activity + Cert) | ❌ | ❌ | ✅ |
| Free & open source | ❌ | ❌ | ✅ |

---

## 🚀 Features

### 📤 Smart Multi-File Upload
- Upload up to 3 Excel files simultaneously: **GPA transcript**, **activity & awards**, **certificates**
- Auto-detects file type from filename and content
- Parses Vietnamese academic format: semester GPA tables, award levels (Quốc tế / Quốc gia / Thành phố), test scores

### 📊 Capability Analysis (SPSS-equivalent)
- **GPA Trend Table** — average GPA per semester across 5 semesters (HK1 Lớp 10 → HK1 Lớp 12)
- **Subject Stats Table** — mean, std deviation, min/max, trend direction per subject
- **Strength Breakdown** — normalized scores across STEM, Language, International Certificates, Activities, Research & Awards
- **Key Insights** — plain-language bullet points about the student's standout qualities
- **Strengths & Gaps** — actionable items for scholarship competitiveness

### 🎓 Scholarship Opportunities
- AI web search via OpenAI for real, current scholarship opportunities matched to student tier
- Match score (0–100%) per university based on GPA, test scores, awards, activities
- Filter by **Mơ ước / Phù hợp / An toàn** (dream / target / safety)
- Deadline, amount (USD/yr), GPA requirement displayed in a clean table
- Match reasons explained per opportunity

### 🗓 Personalized Roadmap
- Month-by-month milestones from current date to application deadline
- Phases: **improve → prep → apply → wait**
- Priority-coded (high / medium / low) with actionable notes

### 🎮 Simulate Bar
- Select any matched university and any criterion (GPA, SAT, IELTS, TOEFL, award rank, activities)
- Adjust via slider or option selector
- Instantly see predicted match score change with visual progress bar

### 🔐 Authentication
- Clerk-powered sign-in/sign-up (email + social providers)
- Auth-gated `/app` route
- User data synced to Supabase

---

## 🏗️ Tech Stack

### Backend
| Technology | Purpose |
|------------|---------|
| Python 3.11+ | Runtime |
| FastAPI | Web framework |
| NumPy + Pandas | Statistical computation |
| OpenAI GPT-4o / GPT-4o-mini | LLM for intent parsing, insights, web search |
| Supabase | PostgreSQL metadata storage |
| Cloudflare R2 | Object storage (S3-compatible) |
| Clerk | Authentication |

### Backend — Student Analysis Pipeline
| Module | Purpose |
|--------|---------|
| `backend/student/profile_extractor.py` | Multi-file Excel parser (GPA, Activity, Certificate) |
| `backend/student/analyzer.py` | SPSS-equivalent capability analysis |
| `backend/student/scholarship_searcher.py` | AI web search for matching scholarships |
| `backend/student/roadmap.py` | Personalized roadmap generator |
| `backend/llm/web_search.py` | OpenAI web search integration |

### Frontend
| Technology | Purpose |
|------------|---------|
| Next.js 16 | React framework (App Router, Turbopack) |
| React 19 | UI library |
| TypeScript 5 | Type safety |
| Tailwind CSS 4 | Styling |
| Zustand 5 | State management |
| Framer Motion 12 | Animations |
| Clerk | Authentication UI |

---

## 🛠️ Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- npm 9+
- OpenAI API key (with web search access)

### 1. Clone the repo

```bash
git clone https://github.com/sotaworksvn/statworks.git
cd statworks
git checkout edtech-etest
```

### 2. Backend setup

```bash
cp backend/.env.example backend/.env    # Add OPENAI_API_KEY
pip install -e backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend setup

```bash
cd frontend
cp .env.local.example .env.local    # Add NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
npm install
npm run dev
```

### 4. Test with sample data

Upload the 3 Excel files from `dataset/THPT1_NguyenVanAn_*.xlsx`, then ask:

> *"Dựa trên dữ liệu của Nguyễn Văn An, hãy phân tích và cho tôi biết cơ hội học bổng"*

> 📖 Detailed guides: [Backend](.docs/guide-line/01-backend.md) · [LLM](.docs/guide-line/02-llm.md) · [Frontend](.docs/guide-line/03-frontend.md) · [Deployment](.docs/guide-line/04-deployment.md)

---

## 📁 Project Structure

```
sota-statworks-pro/
├── backend/                     # FastAPI backend
│   ├── main.py                  # App entry point, CORS, routers
│   ├── upload.py                # POST /upload (multi-file support)
│   ├── analyze.py               # POST /analyze (full AI pipeline)
│   ├── student/                 # EdTech analysis pipeline
│   │   ├── profile_extractor.py # Multi-file Excel parser
│   │   ├── analyzer.py          # SPSS-equivalent capability analysis
│   │   ├── scholarship_searcher.py  # AI web search for scholarships
│   │   └── roadmap.py           # Personalized roadmap generator
│   ├── engines/                 # Statistical engines (OLS, PLS-SEM)
│   ├── llm/                     # LLM integration (parser, insight, web_search)
│   ├── scholarship/             # Scholarship matching & simulation
│   ├── db/                      # Supabase client
│   └── tests/                   # Backend tests
├── frontend/                    # Next.js frontend
│   ├── app/                     # App Router pages
│   ├── components/
│   │   ├── student/             # StudentProfilePanel (6-section EdTech UI)
│   │   └── app/                 # Chat, upload, insight panels
│   └── lib/                     # API client, store, types
├── dataset/                     # Sample student data (3 profiles × 3 files)
│   ├── THPT1_NguyenVanAn_*.xlsx
│   ├── THPT2_TranThiBaoChau_*.xlsx
│   └── THCS_LeHoangMinh_*.xlsx
├── .docs/                       # Documentation
└── LICENSE                      # AGPL-3.0
```

---

## 🧪 Testing

```bash
# Run all backend tests
python -m pytest backend/tests/ -v

# Quick pipeline smoke test (requires backend running)
python -c "
import pandas as pd
from backend.student.profile_extractor import extract_student_profile_full
dfs = {
  'GPA.xlsx': pd.read_excel('dataset/THPT1_NguyenVanAn_GPA.xlsx'),
  'HoatDong.xlsx': pd.read_excel('dataset/THPT1_NguyenVanAn_HoatDong.xlsx'),
  'ChungChi.xlsx': pd.read_excel('dataset/THPT1_NguyenVanAn_ChungChi.xlsx'),
}
p = extract_student_profile_full(dfs)
print(p['name'], '|', p['overall_tier'], '|', p['composite_score'])
# → Nguyễn Văn An | Top 1% | 92.1
"

# Frontend type-check
cd frontend && npx tsc --noEmit
```

---

## 🌐 Deployment

| Component | Platform | Guide |
|-----------|----------|-------|
| Backend   | [Render.com](https://render.com) | [Deployment Guide](.docs/guide-line/04-deployment.md#2-backend--rendercom) |
| Frontend  | [Vercel](https://vercel.com) | [Deployment Guide](.docs/guide-line/04-deployment.md#3-frontend--vercel) |

> ⚠️ **Security:** All API keys and secrets are set via platform environment variables. Never commit secrets to the repository.

---

## 👥 Team

<div align="center">

**Phú Nhuận Builder × SOTA Works**

</div>

| Name | Role | GitHub |
|------|------|--------|
| **Nguyễn Ngọc Gia Bảo** | Team Leader · Fullstack Dev | [@bernieweb3](https://github.com/bernieweb3) |
| **Đặng Đình Tiến** | UI/UX Advisor · Tester | [@Kaitobaee](https://github.com/Kaitobaee) |
| **Đỗ Phúc Duy** | Tester · Pitching Personnel | [@dophucduy](https://github.com/dophucduy) |

### 📧 Contact

| | Email |
|---|---|
| **Author** | [bernie.web3@gmail.com](mailto:bernie.web3@gmail.com) |
| **Phú Nhuận Builder** | [phunhuanbuilder@gmail.com](mailto:phunhuanbuilder@gmail.com) |
| **SOTA Works** | [sotaworks.vn@gmail.com](mailto:sotaworks.vn@gmail.com) |

---

## 🏆 Hackathon

This project was developed for the **[LotusHacks × HackHarvard × GenAI Fund Vietnam Hackathon 2026](https://lotushack.org)**.

- **Track:** EdTech by ETEST
- **Year:** 2026

---

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

```
SOTA StatWorks
Copyright (C) 2026 Phú Nhuận Builder × SOTA Works

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```
