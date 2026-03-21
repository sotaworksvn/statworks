# SOTA StatWorks — Frontend

> AI-powered statistical decision engine — *"From Data to Decisions, Instantly."*

## Quick Start

```bash
cd frontend && npm install
npm run dev          # → http://localhost:3000
npx tsc --noEmit     # Type-check
npm run build        # Production build
```

## Tech Stack

| Technology | Purpose |
|---|---|
| Next.js 16 (App Router) | Framework |
| React 19 + TypeScript 5 | UI + type safety |
| Tailwind CSS 4 | Styling |
| Zustand 5 | Global state management |
| React Query 5 | Server state / mutations |
| Recharts 3.8 | Driver ranking charts |
| Framer Motion 12 | Micro-animations |
| Clerk 7 | Authentication (Google OAuth) |
| shadcn/ui 4 | Accessible UI components |

## URL Routes

| Route | View |
|---|---|
| `/` | Landing page |
| `/app` | Upload |
| `/app/chat` | AI Chat |
| `/app/viewer` | Data Viewer |
| `/app/monitor` | Monitor (Data Analysis) |
| `/app/monitor/data-analysis` | Monitor → Data Analysis |
| `/app/monitor/impact-analysis` | Monitor → Impact Analysis |
| `/app/history/chat` | History → AI Chat |
| `/app/history/viewer` | History → Data Edits |
| `/app/history/monitor` | History → Monitor |

## Environment Variables

```dotenv
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
```

## Deploy

Deployed to **Vercel** via `git push main`. Set env vars in Vercel dashboard.

---

## Team — Phú Nhuận Builder x SOTA Works

| Name | Role |
|---|---|
| Nguyễn Ngọc Gia Bảo | Team Leader · Backend Dev · Frontend Dev · OpenAI API Integration |
| Đặng Đình Tiến | Vice Leader · Frontend Dev · Tester |
| Đỗ Phúc Duy | Frontend Dev · Tester · Pitching Personnel |
