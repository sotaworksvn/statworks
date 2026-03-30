# SOTA StatWorks — Frontend Guide

| Field            | Value                                                           |
|------------------|-----------------------------------------------------------------|
| **Last updated** | 2026-03-21                                                      |
| **Version**      | 0.2.0                                                           |
| **Stack**        | Next.js 16 · React 19 · TypeScript 5 · Tailwind CSS 4 · Zustand |
| **Source**       | `frontend/` directory                                           |

---

## 1. Quick Start

```bash
# Install dependencies (from project root)
cd frontend && npm install

# Run dev server
npm run dev          # → http://localhost:3000

# Type-check
npx tsc --noEmit

# Production build
npm run build
```

> **Note:** Copy `.env.local.example` to `.env.local` before first run. See §6 for required variables.

---

## 2. Project Structure

```
frontend/
├── app/
│   ├── layout.tsx              # Root layout — fonts, metadata, Providers wrapper
│   ├── page.tsx                # Landing page (/)
│   ├── globals.css             # Tailwind CSS v4 + custom design tokens
│   └── app/
│       ├── layout.tsx          # App layout (full-height flex)
│       ├── page.tsx            # Redirect to [[...slug]]
│       └── [[...slug]]/
│           └── page.tsx        # Catch-all route — URL↔Zustand sync
├── components/
│   ├── providers.tsx           # ClerkProvider, QueryClientProvider, AuthSync
│   ├── app/
│   │   ├── header.tsx          # App header — logo, dataset info, UserButton
│   │   ├── upload-zone.tsx     # Drag-and-drop file upload (react-dropzone)
│   │   ├── chat-panel.tsx      # Chat panel — user questions + AI responses
│   │   ├── insight-panel.tsx   # Insight panel — summary, driver ranking chart, recommendation
│   │   ├── simulation-bar.tsx  # Simulation controls — variable select, delta slider, results
│   │   ├── sidebar.tsx         # Canva-style sidebar — light gradient, logo toggle, router.push nav
│   │   ├── dashboard.tsx       # Monitor page — Data Analysis + Impact Analysis tabs with ribbons
│   │   ├── data-viewer.tsx     # Data Viewer — browser-tab file viewer with inline editing
│   │   ├── history-view.tsx    # History — 3-tab ribbon (Chat, Data Edits, Monitor) with date filters
│   └── ui/                    # shadcn/ui primitives (button, skeleton, select, etc.)
├── hooks/
│   └── use-auth-sync.ts       # Auto-sync Clerk user → backend /sync-user
├── lib/
│   ├── api.ts                 # Backend API client (upload, analyze, simulate, syncUser)
│   ├── store.ts               # Zustand global state (auth, upload, analysis, simulation)
│   ├── types.ts               # TypeScript interfaces (UploadResult, InsightResult, etc.)
│   └── utils.ts               # cn() utility for Tailwind class merging
└── public/
    ├── logo.png               # SOTA StatWorks logo
    ├── phunhuanbuilder.png    # Phú Nhuận Builder team logo
    └── sotaworks.png          # SOTA Works team logo
```

---

## 3. Key Libraries

| Library              | Purpose                                    |
|----------------------|--------------------------------------------|
| `next` 16.2          | Framework (App Router, Turbopack)          |
| `react` 19.2         | UI library with React Compiler             |
| `@clerk/nextjs` 7    | Authentication (sign-in, sign-up, session) |
| `zustand` 5          | Lightweight global state management        |
| `@tanstack/react-query` 5 | Server state, mutation management    |
| `recharts` 3.8       | Responsive charts (Driver Ranking bar chart) |
| `framer-motion` 12   | Page transitions, micro-animations         |
| `react-dropzone` 15  | Drag-and-drop file upload UI               |
| `sonner` 2           | Toast notifications                        |
| `tailwindcss` 4      | Utility-first CSS framework                |
| `shadcn/ui` 4        | Pre-built accessible UI components         |

---

## 4. Pages & Routes

| Route  | Component               | Description                                    |
|--------|-------------------------|------------------------------------------------|
| `/`    | `app/page.tsx`          | Landing page with hero, features, team section |
| `/app` | `app/app/[[...slug]]/page.tsx` | Main workspace — auth-gated, catch-all route |
| `/app/chat` | ^                  | AI Chat view                                   |
| `/app/viewer` | ^              | Data Viewer                                    |
| `/app/monitor` | ^             | Monitor (default: Data Analysis tab)           |
| `/app/monitor/data-analysis` | ^ | Monitor → Data Analysis tab               |
| `/app/monitor/impact-analysis` | ^ | Monitor → Impact Analysis tab           |
| `/app/history` | ^             | History (default: AI Chat tab)                 |
| `/app/history/chat` | ^        | History → AI Chat tab                          |
| `/app/history/viewer` | ^      | History → Data Edits tab                       |
| `/app/history/monitor` | ^     | History → Monitor tab                          |

### `/app` Auth Flow

```
User navigates to /app
    │
    ├── Clerk not loaded → Loading spinner
    │
    ├── Not signed in → Clerk <SignIn /> component (hash routing)
    │
    └── Signed in → AuthSync hook → Show app workspace
                        │
                        ├── No dataset → UploadZone
                        │
                        └── Dataset loaded → ChatPanel + InsightPanel + SimulationBar
```

---

## 5. State Management (Zustand)

The global store at `lib/store.ts` manages:

| Slice        | State                                    | Key actions                    |
|--------------|------------------------------------------|--------------------------------|
| **Auth**     | `user: ClerkUser \| null`                | `setUser()`                    |
| **Upload**   | `fileId`, `datasetName`, `columns`, `rowCount` | `setUploadState()`, `resetDataset()` |
| **Analysis** | `insight: InsightResult \| null`         | `setInsight()`, `setIsAnalyzing()` |
| **Simulation** | `simulation: SimulationResult \| null` | `setSimulation()`, `setIsSimulating()` |

`resetDataset()` clears all derived state (insight, simulation, errors) when switching datasets.

---

## 6. Environment Variables

Create `frontend/.env.local`:

```dotenv
# Backend API endpoint
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

# Clerk publishable key (from https://dashboard.clerk.com → API Keys)
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
```

| Variable                             | Required | Description                    |
|--------------------------------------|----------|--------------------------------|
| `NEXT_PUBLIC_BACKEND_URL`            | **Yes**  | Backend API base URL           |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`  | No       | Clerk auth (anonymous mode if missing) |

> **Security:** Only `NEXT_PUBLIC_*` variables are exposed to the browser. Never put secret keys here.

---

## 7. API Client (`lib/api.ts`)

All backend calls go through typed helper functions:

| Function               | Endpoint               | Auth header          |
|------------------------|-----------------------|----------------------|
| `uploadFile(files)`    | `POST /api/upload`    | `x-clerk-user-id`   |
| `analyzeDataset(fileId, query)` | `POST /api/chat/analyze` | `x-clerk-user-id` |
| `simulateScenario(fileId, var, delta)` | `POST /api/monitor/simulate` | `x-clerk-user-id` |
| `syncUser(clerkId, email, name)` | `POST /api/auth/sync-user` | —          |

All functions throw on non-2xx responses with the parsed error `detail` message.

---

## 8. Typography

Two font families loaded via `next/font/google` in `layout.tsx`:

| Font               | CSS Variable         | Usage                          |
|--------------------|----------------------|--------------------------------|
| **Press Start 2P** | `--font-press-start` | Section headings, labels (decorative) |
| **Poppins**        | `--font-poppins`     | Body content, UI elements (primary) |

Apply via Tailwind: `font-pixel` (Press Start 2P) or default (Poppins).

---

## 9. Component Details

### UploadZone
- Accepts `.csv`, `.xlsx` (primary) and `.docx`, `.pptx` (context)
- Drag-and-drop + click-to-browse via `react-dropzone`
- Shows upload progress bar during transfer
- Calls `uploadFile()` and updates Zustand store on success

### ChatPanel
- Left 35% of the workspace
- Displays conversation history (user bubbles + AI response)
- Suggestion chips for quick questions
- Calls `analyzeDataset()` via React Query mutation

### InsightPanel
- Right 65% of the workspace
- Executive summary card (highlight bg)
- Driver Ranking horizontal bar chart (Recharts)
  - X-axis: Impact Strength (with tick marks and grid lines)
  - Y-axis: Driver names
  - Color: green (positive) / red (negative)
  - Tooltip: impact value, p-value, significance
- Actionable recommendation card
- Collapsible Model Details (model type, R², confidence, decision trace)

### SimulationBar
- Fixed footer bar, only visible after analysis
- Variable dropdown (from driver names)
- Delta slider (-50% to +50%)
- Simulate button → API call → animated ResultBadge
- Inline error display for stale sessions

---

## 10. Development Workflow

### Local Dev Checklist

1. Start backend (from project root): `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
2. Start frontend: `cd frontend && npm run dev`
3. Open [http://localhost:3000](http://localhost:3000)
4. Sign in via Clerk → Upload dataset → Ask question → Simulate

### Build & Type-check

```bash
npx tsc --noEmit     # Type errors
npm run lint          # ESLint
npm run build         # Production build
```

### Clearing Cache

If Turbopack cache gets corrupted:

```bash
# Stop dev server first, then:
rm -rf frontend/.next
npm run dev
```
