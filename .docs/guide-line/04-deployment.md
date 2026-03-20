# SOTA StatWorks — Deployment Guide

| Field            | Value                                |
|------------------|--------------------------------------|
| **Last updated** | 2026-03-21                           |
| **Backend**      | Render.com (Python Web Service)      |
| **Frontend**     | Vercel (Next.js)                     |
| **Source**       | `backend/render.yaml` · `frontend/` |

---

## 1. Architecture Overview

```
┌──────────┐       HTTPS        ┌──────────────┐
│  Vercel  │  ←───────────────→  │  Render.com  │
│ (Next.js)│   API calls to     │  (FastAPI)   │
│ frontend │   BACKEND_URL      │   backend    │
└──────────┘                    └──────┬───────┘
                                       │
                          ┌────────────┼────────────┐
                          │            │            │
                    ┌─────┴──┐  ┌─────┴──┐  ┌─────┴──┐
                    │Supabase│  │  R2    │  │ OpenAI │
                    │ (DB)   │  │(Files) │  │ (LLM)  │
                    └────────┘  └────────┘  └────────┘
```

---

## 2. Backend → Render.com (Free Tier)

### 2.1 Prerequisites

- A free [Render.com](https://render.com) account
- GitHub repository connected to Render

> **Reference config:** `backend/render.yaml` contains the service definition for reference. You'll enter these settings manually in the Render dashboard (no Blueprint needed — that costs money).

### 2.2 Create Web Service (Free)

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Configure:

| Setting            | Value                                                        |
|--------------------|------------------------------------------------------------- |
| **Name**           | `sota-statworks-api`                                         |
| **Runtime**        | Python                                                       |
| **Root Directory** | *(leave empty — deploy from project root)*                   |
| **Build Command**  | `pip install -r backend/requirements.txt`                    |
| **Start Command**  | `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`      |
| **Health Check**   | `/health`                                                    |
| **Plan**           | **Free** (select Free instance type)                         |

### 2.3 Environment Variables

Set these in **Render Dashboard → Environment** (NOT in code or `render.yaml`):

> ⚠️ **NEVER commit secrets to the repository.** All secrets are set via Render's dashboard only.

| Variable               | Required  | How to get it                              |
|------------------------|-----------|--------------------------------------------|
| `DEV_MODE`             | Yes       | Set to `false` for production              |
| `CORS_ORIGIN`          | Yes       | Your Vercel URL (e.g., `https://sota-statworks.vercel.app`) |
| `OPENAI_API_KEY_1`     | Yes       | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `OPENAI_API_KEY_2`–`4` | No       | Additional keys for rotation (optional)    |
| `SUPABASE_URL`         | Recommended | [supabase.com](https://supabase.com) → Project → Settings → API |
| `SUPABASE_SERVICE_KEY` | Recommended | Same location, use **service_role** key    |
| `R2_ACCOUNT_ID`        | Recommended | [Cloudflare Dashboard](https://dash.cloudflare.com) → R2 |
| `R2_ACCESS_KEY_ID`     | Recommended | R2 → API Tokens → Create token            |
| `R2_SECRET_ACCESS_KEY` | Recommended | Same token creation page                   |
| `R2_BUCKET_NAME`       | Recommended | R2 → Create bucket                        |
| `CLERK_SECRET_KEY`     | Recommended | [dashboard.clerk.com](https://dashboard.clerk.com) → API Keys |

### 2.4 Verify Deployment

```bash
# Check health (replace with your Render URL)
curl https://sota-statworks-api.onrender.com/health
# Expected: {"status":"ok"}
```

### 2.5 Pre-Demo Checklist

- [ ] `DEV_MODE=false`
- [ ] `CORS_ORIGIN` matches exact Vercel URL
- [ ] At least `OPENAI_API_KEY_1` is set
- [ ] Hit `/health` 5 minutes before demo (Render free tier cold-starts ~30s)
- [ ] Test full flow: upload → analyze → simulate

---

## 3. Frontend → Vercel

### 3.1 Prerequisites

- A [Vercel](https://vercel.com) account
- GitHub repository connected to Vercel

### 3.2 Setup

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Click **Add New** → **Project**
3. Import your GitHub repo
4. Configure:

| Setting              | Value                       |
|----------------------|-----------------------------|
| **Framework Preset** | Next.js (auto-detected)     |
| **Root Directory**   | `frontend`                  |
| **Build Command**    | `npm run build`             |
| **Output Directory** | `.next` (default)           |
| **Node.js Version**  | 20.x                        |

5. Click **Deploy**

### 3.3 Environment Variables

Set in **Vercel Dashboard → Settings → Environment Variables**:

> ⚠️ **NEVER commit secrets to the repository.** Only `NEXT_PUBLIC_*` variables are browser-safe.

| Variable                            | Value                                        | Scope      |
|-------------------------------------|----------------------------------------------|------------|
| `NEXT_PUBLIC_BACKEND_URL`           | Your Render backend URL (e.g., `https://sota-statworks-api.onrender.com`) | Production |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Your Clerk **publishable** key (`pk_live_...` or `pk_test_...`) | Production |

### 3.4 Verify Deployment

1. Open your Vercel URL (e.g., `https://sota-statworks.vercel.app`)
2. Landing page should load
3. Click **Launch App** → Clerk sign-in should appear
4. Sign in → Upload dataset → Ask question → Verify results

---

## 4. Connecting Backend ↔ Frontend

The critical link is **CORS**:

```
Frontend (Vercel)                  Backend (Render)
NEXT_PUBLIC_BACKEND_URL  ──────→  CORS_ORIGIN must match
                                  the Vercel domain exactly
```

### Common CORS Mistakes

| Mistake                        | Fix                                    |
|--------------------------------|----------------------------------------|
| Trailing slash in CORS_ORIGIN  | Remove it: `https://app.vercel.app`    |
| Using `http://` instead of `https://` | Vercel always uses HTTPS        |
| Wildcard `*` in production     | Set the exact Vercel URL               |

---

## 5. Security Checklist

> These rules are **mandatory** before any public deployment.

- [ ] **No secrets in code**: All API keys are set via platform dashboards only
- [ ] **`.env` is gitignored**: Verify `backend/.env` and `frontend/.env.local` are in `.gitignore`
- [ ] **`DEV_MODE=false`** in production: Enables API key validation
- [ ] **CORS is locked**: `CORS_ORIGIN` set to exact Vercel URL, not `*`
- [ ] **Clerk keys separated**: `pk_live_*` (publishable, safe) vs `sk_live_*` (secret, backend only)
- [ ] **Supabase service key**: Only on Render backend, never on Vercel frontend
- [ ] **R2 credentials**: Only on Render backend, never exposed to frontend

---

## 6. Monitoring & Troubleshooting

### Backend Logs (Render)

- Go to Render Dashboard → Service → **Logs**
- Watch for `WARNING` logs about latency (>1.8s) or LLM failures

### Frontend Errors (Vercel)

- Go to Vercel Dashboard → Deployment → **Functions** tab
- Check Runtime Logs for SSR errors

### Common Issues

| Symptom                              | Cause                                  | Fix                                    |
|--------------------------------------|----------------------------------------|----------------------------------------|
| CORS error in browser console        | `CORS_ORIGIN` doesn't match Vercel URL | Update Render env var                  |
| `NEXT_PUBLIC_BACKEND_URL is not set` | Missing env var in Vercel              | Add to Vercel Environment Variables    |
| Backend returns 404 after redeploy   | In-memory store wiped on restart       | Re-upload dataset (expected behavior)  |
| Clerk sign-in not appearing          | Missing publishable key                | Add `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` |
| Cold start ~30s on first request     | Render free tier spin-down             | Hit `/health` before demo             |

---

## 7. Production Upgrade Path

| Concern             | Free Tier Limitation          | Upgrade Option                 |
|---------------------|-------------------------------|--------------------------------|
| Cold starts         | 30s spin-down on Render Free  | Render Starter plan ($7/mo)    |
| Persistent storage  | In-memory store lost on restart | Already handled via Supabase + R2 |
| Custom domain       | `.onrender.com` / `.vercel.app` | Add custom domain on both platforms |
| SSL                 | Auto-provisioned              | Included on both platforms     |
