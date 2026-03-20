# SOTA StatWorks — Product Requirements Document

| Field        | Value                        |
|--------------|------------------------------|
| **Status**   | `draft`                      |
| **Team**     | Phú Nhuận Builder x SOTA Works |
| **Project**  | SOTA StatWorks               |
| **Created**  | 2026-03-20                   |
| **Last updated** | 2026-03-20               |
| **Version**  | 0.2                          |

---

## 1. Problem

### Who has the problem

**Business analysts, product managers, marketers, economics students, and researchers** who hold structured datasets (Excel/CSV) and need to understand *what drives* a key business outcome — but lack the statistical training to operate tools like SPSS or SmartPLS.

### What it costs them

| Pain point | Current cost |
|---|---|
| Tool complexity | Hours of learning SPSS / SmartPLS UI before any insight is produced |
| Output ≠ Decision | Tools return `p-values` and `coefficients`; users cannot translate numbers into actions |
| Fragmented workflow | Data lives in Excel → analysis in SPSS → narrative in PowerPoint → decision delayed by days |
| No simulation | No existing lightweight tool lets a non-expert ask "what happens if I improve X by 20%?" |

### How they cope today

Users either hire specialist analysts (expensive, slow) or rely on generic AI chat tools (ChatGPT etc.) that provide text commentary but perform no real statistical computation and cannot simulate outcomes.

---

## 2. Why Now

| Driver | Detail |
|---|---|
| **LLM orchestration maturity** | OpenAI API models (`gpt-5.4-mini` for structured parsing, `gpt-5.4` for insight generation) provide production-grade structured output with a 400K context window (mini) and up to 1.05M tokens (flagship). Sponsored API credits from the organiser ($400 total across 4 accounts) remove cost as a constraint for the demo. |
| **Competition gap** | SPSS is complex and desktop-locked; SmartPLS requires an academic diagram-based setup; generic AI tools produce no real statistical output. No single product bridges the gap for business users. |
| **Demo-first opportunity** | A hackathon context creates a forcing function to prove the concept end-to-end within 20–30 hours — validating whether a chat-first statistical engine can wow non-expert judges. |
| **Python ML ecosystem** | `numpy`, `scipy`, `pandas`, `FastAPI` provide a mature, buildable backend that can replicate SPSS OLS regression and SmartPLS PLS-SEM in a fraction of the traditional setup time. |

---

## 3. Success Criteria

| Metric | Target | Measurement Method |
|---|---|---|
| Time to first insight | ≤ 60 seconds from file upload to rendered recommendation | Stopwatch during demo run |
| API response time | < 2 seconds end-to-end for `/analyze` | FastAPI response timing logs |
| Simulation update latency | < 1 second after slider interaction | Frontend performance trace |
| Correct driver identification | Top driver matches ground-truth for a prepared demo dataset | Manual validation with known dataset |
| Judge/user comprehension | User understands the recommendation without statistical background | Demo observation — no follow-up clarification needed |
| LLM call budget per request | ≤ 2 LLM calls, ≤ 1k tokens per request | Token usage logs from OpenAI API dashboard |
| Fallback stability | System returns a valid result 100% of the time, even when LLM output is malformed | Manual adversarial test with garbled queries |

---

## 4. User Needs and Scenarios

### Need 1 — Understand what drives an outcome without statistical expertise

> "I have survey data. I want to know what most affects customer retention — but I don't know SPSS."

**Scenario A — Marketing analyst:**
A marketer uploads an Excel file with columns `Trust`, `UX`, `Price`, `Retention`. She types: *"What affects retention?"* The system returns: *"Trust is the strongest driver of retention (impact score 0.62). UX follows. Price has minimal effect."* No statistical terms are visible unless she expands the details panel.

**Scenario B — Economics student:**
A student uploads a cross-country dataset with `GDP`, `Education`, `Corruption`, `Freedom Index`. He asks: *"What explains freedom index?"* The system runs a regression or PLS-SEM automatically and surfaces the ranked drivers in plain English.

---

### Need 2 — Simulate the impact of a proposed change before committing resources

> "If we invest in improving trust by 20%, how much does retention improve?"

**Scenario — Product manager:**
After seeing the driver ranking, a PM drags the `Trust` slider to +20%. The interface instantly updates: *"Expected retention increase: +12.4%."* No formulas are visible. The PM can present this estimate in a meeting within seconds.

---

### Need 3 — Use context from multiple file types (not just structured data)

> "I have an Excel dataset AND a PowerPoint with our company's strategy notes."

**Scenario — Business analyst:**
An analyst uploads both a `.xlsx` data file and a `.pptx` context deck. The system extracts the structured data from Excel as the primary dataset and absorbs the Word/PPT content as contextual background, allowing the AI to produce insight that sounds like it was written by a domain analyst — not just a statistical engine.

---

### Need 4 — Get a decision, not a report

> "After seeing the analysis, I need to know what to do next — not what the numbers mean."

**Scenario — Any user:**
Every insight view ends with an explicitly labelled **Recommendation** card — e.g., *"Focus resources on improving Trust. It delivers the highest return on retention."* This card is always visible without scrolling.

---

### Need 5 — Resume a session without re-uploading data

> "I uploaded my dataset yesterday. When I come back today, I don't want to re-upload — I want to see my previous results instantly."

**Scenario — Judge / returning user:**
A hackathon judge logs in via Google, uploads a dataset, reviews insights, then closes the browser. The next day (or during a second demo round), the judge logs in again and sees the same dataset and analysis results immediately — no re-upload, no re-analysis. This is enabled by persistent storage (Cloudflare R2 for files, Supabase for metadata) and identity (Clerk for login).

---

## 5. Scope

### In Scope (v1 — Hackathon Demo)

| Area | What is included |
|---|---|
| **Data ingestion** | Upload of `.xlsx`, `.csv` (primary data); `.docx`, `.pptx` (context/text extraction only) |
| **Statistical engine** | OLS regression (SPSS-style) and PLS-SEM (SmartPLS-style), auto-selected via scoring function |
| **AI layer** | LLM-powered intent parsing and variable extraction via `gpt-5.4-mini` (Call 1); insight generation via `gpt-5.4` (Call 2). Accessed via OpenAI API with sponsored credits. |
| **Scenario simulation** | Single-variable delta propagation (1-hop and multi-hop via directed graph) |
| **Core endpoints** | `POST /upload`, `POST /analyze`, `POST /simulate` |
| **Authentication** | Clerk-based Google OAuth login; session management; user identity passed to backend via `x-clerk-user-id` header |
| **Metadata persistence** | Supabase (PostgreSQL) for user records, dataset metadata, and analysis results |
| **Object storage** | Cloudflare R2 for raw dataset files and analysis output; presigned URL upload/download |
| **Frontend** | Single-screen Next.js app: Chat panel (input), Insight panel (output), Simulation bar (bottom), identity-aware UI |
| **UX** | Progressive reveal, micro-animations, slider-based simulation, no statistics jargon in default view, persistent session resume |
| **Insight output** | Summary sentence, ranked driver chart, actionable recommendation card, collapsible model details |
| **Reliability** | LLM retry (×2), validation layer filtering hallucinated variables, hard fallback to regression + top numeric columns |

### Out of Scope (v1)

| Exclusion | Rationale |
|---|---|
| Full academic PLS (HTMT, AVE, discriminant validity reports) | Over-engineered for demo; adds complexity without decision value |
| Multi-page or tabbed navigation | Violates single-screen paradigm; reduces wow factor |
| Real-time / streaming data ingestion | Outside the 20–30h build window |
| Automated report PDF generation | Nice-to-have; deferred to future version |
| Celery / Redis async queue (bootstrap > 500) | Optional; only added if bootstrap performance is a bottleneck |
| Chat conversation history / memory | Stateless MVP is sufficient for demo |
| Multi-language UI (i18n) | English-only for v1 |

---

## 6. Risks and Assumptions

### Risks

| Risk | Likelihood | Impact | Why it exists | Mitigation |
|---|---|---|---|---|
| LLM returns malformed JSON despite JSON mode | Low | High | Even `gpt-4o-mini` can occasionally deviate in edge cases | Validation layer strips unknown fields; fallback auto-selects numeric columns as features |
| Bootstrap on large datasets exceeds 2s response target | Medium | Medium | Statistical resampling is CPU-intensive | Cap bootstrap samples at 200 for demo; Celery queue is optional upgrade |
| Judge uploads edge-case dataset (non-numeric, all-missing) | Low | High | Real-world data is messy | Pre-validate column types on upload; surface a clear error message; offer a demo dataset |
| PLS scoring function misclassifies model choice | Low | Medium | Scoring weights are heuristic, not empirically validated | Default to regression if in doubt; log the decision trace for transparency |
| OpenAI API rate limit hit during demo | Low | Low | Demo uses ≤ 2 calls/request; total requests are minimal; $400 credit budget is unconstrained | Keep an API key from each of the 4 accounts on standby for immediate rotation |

### Assumptions

| Assumption | What breaks if wrong |
|---|---|
| Demo dataset is well-curated (clean, numeric, 50–500 rows) | Model output quality degrades; R² drops; insight may be misleading |
| OpenAI API is reachable and at least one account has remaining credit at demo time | Fallback to a second account key (4 accounts available); worst case: use template-generated insight strings |
| Users query in English | Intent parsing prompt is English-only; non-English queries will fail to extract variables correctly |
| A single upload session per demo (no concurrent users) | Stateless design does not handle session isolation; concurrent uploads may collide |

---

## 7. Constraints

| Constraint | Detail |
|---|---|
| **Build window** | 20–30 hours total (hackathon timeline) |
| **Demo duration** | ≤ 5 minutes; every user action must complete in ≤ 10 seconds |
| **LLM cost** | OpenAI API with sponsored credits: $100 per account × 4 accounts = $400 total. `gpt-5.4-mini` (Call 1): $0.75/1M input, $4.50/1M output — ~$0.00075/request. `gpt-5.4` (Call 2): $2.50/1M input, $15.00/1M output — ~$0.0025/request. Total per `/analyze` call: ~$0.003. Budget is effectively unconstrained for demo scale. |
| **Tech stack** | Backend: FastAPI + Python; Frontend: Next.js (App Router) + TypeScript + TailwindCSS; Charts: Recharts; Animation: Framer Motion; Auth: Clerk (`@clerk/nextjs`); DB: Supabase (`supabase-py`); Storage: Cloudflare R2 (`boto3`) |
| **Target devices** | Desktop browser only (1280px+ viewport); no mobile breakpoints required for v1 |
| **Persistence layer** | Supabase (PostgreSQL) for metadata; Cloudflare R2 for dataset files. In-memory store remains as a cache layer for fast access to the latest dataset. |

---

## 8. Open Points

| # | Question | Context | Options |
|---|---|---|---|
| OP-1 | What is the minimum dataset size for PLS to be meaningful? | PLS requires sufficient observations per latent variable to avoid degenerate output | (a) Enforce ≥ 30 rows hard gate; (b) Warn user but proceed; (c) Auto-switch to regression below threshold |
| OP-2 | Should the Simulation Bar show confidence intervals on the predicted delta? | Showing ± range is more honest but adds complexity to the UI | (a) Show point estimate only (simpler, faster); (b) Show 95% CI from bootstrap |
| OP-3 | Should the app support multi-target analysis in v1? | User might ask "What affects both retention AND satisfaction?" | (a) Single-target only (simpler); (b) Multi-target with tabbed results (out of scope for now) |
| OP-4 | Demo dataset selection | Judges may want to see their own data vs. a curated demo dataset | (a) Pre-load demo dataset as default; (b) Require upload every time; (c) Offer both via a toggle |
| OP-5 | OpenRouter offline fallback | If API is down during demo, system fails entirely | (a) Pre-cache LLM responses for known demo queries; (b) Accept the risk; (c) Use local LLM (adds setup complexity) |

---

## 9. Related Documents

| Document | Path | Status |
|---|---|---|
| Backend Blueprint | _(source brief — see conversation context)_ | Reference |
| AI Layer Blueprint | _(source brief — see conversation context)_ | Reference |
| Frontend Blueprint | _(source brief — see conversation context)_ | Reference |
| UI/UX Design System | _(source brief — see conversation context)_ | Reference |
| System Design | `.docs/02-system-design.md` | `draft` |
| Feature Specifications | `.docs/03-features-spec.md` | `draft` |
| Development Rules | `.docs/04-rule.md` | `draft` |
| Task Plan | `.docs/05-tasks-plan.md` | `draft` |
| Codebase Summary | `.docs/03-codebase-summary.md` | Not yet created |
| ADR-0001 — Clerk Authentication | `docs/adrs/0001-clerk-authentication.md` | `proposed` |
| ADR-0002 — Supabase Metadata | `docs/adrs/0002-supabase-metadata.md` | `proposed` |
| ADR-0003 — Cloudflare R2 Storage | `docs/adrs/0003-cloudflare-r2-storage.md` | `proposed` |

### Downstream Specs

- `.docs/03-features-spec.md` — F-01 through F-05

---

## Appendix — Product Identity Reference

| Field | Value |
|---|---|
| **Product name** | SOTA StatWorks |
| **Team** | Phú Nhuận Builder x SOTA Works |
| **Tagline** | *"From Data to Decisions — Instantly."* |
| **One-liner** | SOTA StatWorks is an AI-powered decision engine that transforms raw data into actionable insights and simulations — without requiring statistical expertise. |
| **Primary users** | Product managers, marketers, business analysts, economics students, researchers |
| **Core differentiator vs. SPSS** | AI auto-selects the model; outputs decisions, not coefficient tables |
| **Core differentiator vs. SmartPLS** | Chat-driven, zero setup, business-friendly language |
| **Core differentiator vs. generic AI** | Real statistical computation (OLS, PLS-SEM) + built-in scenario simulation |
