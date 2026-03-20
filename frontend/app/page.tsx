import Image from "next/image";
import Link from "next/link";

/* ─── Landing Page ──────────────────────────────────────────────────────────── */
/* 8 sections per task plan 3.2: Hero, Problem, Solution, How It Works,
   vs. Competitors, Tech Stack, Team, Footer                                    */

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-white">
      {/* ── Nav ─────────────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 flex items-center justify-between px-8 py-4 bg-white/80 backdrop-blur-md border-b border-gray-100">
        <div className="flex items-center gap-3">
          <Image src="/logo.png" alt="SOTA StatWorks" width={180} height={50} priority />
        </div>
        <Link
          href="/app"
          className="rounded-lg bg-[#2D3561] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[#3a4578] transition-colors"
        >
          🚀 Launch App
        </Link>
      </nav>

      {/* ── 1. Hero ─────────────────────────────────────────────────────────── */}
      <section className="relative flex flex-col items-center justify-center px-8 py-28 text-center overflow-hidden">
        {/* Background gradient blobs */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/4 top-0 h-[500px] w-[700px] rounded-full bg-[#FFD700]/10 blur-[120px]" />
          <div className="absolute right-1/4 top-1/4 h-[400px] w-[600px] rounded-full bg-[#E84393]/8 blur-[100px]" />
          <div className="absolute left-1/2 bottom-0 h-[300px] w-[500px] -translate-x-1/2 rounded-full bg-[#4DA8E0]/8 blur-[100px]" />
        </div>

        <div className="relative z-10 flex flex-col items-center gap-6 max-w-4xl">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-[#2D3561]/20 bg-[#2D3561]/5 px-4 py-1.5 text-sm text-[#2D3561] font-medium">
            <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E] animate-pulse" />
            AI-Powered Statistical Decision Engine
          </div>

          {/* Headline */}
          <h1 className="font-pixel text-3xl md:text-4xl lg:text-5xl leading-relaxed tracking-tight">
            <span className="text-gradient-brand">From Data to Decisions</span>
            <br />
            <span className="text-[#1A1A2E]">— Instantly.</span>
          </h1>

          {/* Sub-headline */}
          <p className="text-lg md:text-xl text-gray-500 max-w-2xl leading-relaxed">
            Upload a dataset, ask a question in plain English, get ranked insights
            and real-time simulations — without statistical expertise.
          </p>

          {/* CTA */}
          <Link
            href="/app"
            id="hero-launch-cta"
            className="group mt-4 inline-flex items-center gap-3 rounded-xl bg-[#FF6B4A] px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-[#FF6B4A]/25 transition-all hover:bg-[#e85d3f] hover:shadow-[#FF6B4A]/35 hover:scale-105 active:scale-100"
          >
            🚀 Launch to App
            <span className="transition-transform group-hover:translate-x-1">→</span>
          </Link>
        </div>
      </section>

      {/* ── 2. Problem ──────────────────────────────────────────────────────── */}
      <section className="px-8 py-20 bg-[#F5F5F7]" id="problem">
        <div className="max-w-6xl mx-auto">
          <h2 className="font-pixel text-2xl md:text-3xl text-center text-[#2D3561] mb-4">
            The Problem
          </h2>
          <h5 className="text-center text-gray-500 mb-12 max-w-2xl mx-auto text-lg">
            Current tools weren&#39;t built for decision-makers — they were built for statisticians.
          </h5>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {PROBLEMS.map((p) => (
              <div
                key={p.title}
                className="rounded-2xl bg-white p-8 card-elevated hover:shadow-md transition-shadow"
              >
                <div className="text-3xl mb-4">{p.icon}</div>
                <h3 className="font-semibold text-[#2D3561] text-xl mb-2">{p.title}</h3>
                <p className="text-gray-500 text-base leading-relaxed">{p.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 3. Solution ─────────────────────────────────────────────────────── */}
      <section className="px-8 py-20" id="solution">
        <div className="max-w-6xl mx-auto">
          <h2 className="font-pixel text-2xl md:text-3xl text-center text-[#2D3561] mb-4">
            The Solution
          </h2>
          <h5 className="text-center text-gray-500 mb-12 max-w-2xl mx-auto text-lg">
            One screen. One question. One decision.
          </h5>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {SOLUTIONS.map((s) => (
              <div
                key={s.title}
                className="group rounded-2xl border border-gray-100 bg-white p-8 hover:border-[#FF6B4A]/30 hover:shadow-lg hover:shadow-[#FF6B4A]/5 transition-all"
              >
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-xl bg-[#FF6B4A]/10 text-2xl">
                  {s.icon}
                </div>
                <h3 className="font-semibold text-[#2D3561] text-xl mb-2">{s.title}</h3>
                <p className="text-gray-500 text-base leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 4. How It Works ─────────────────────────────────────────────────── */}
      <section className="px-8 py-20 bg-[#F5F5F7]" id="how-it-works">
        <div className="max-w-4xl mx-auto">
          <h2 className="font-pixel text-2xl md:text-3xl text-center text-[#2D3561] mb-12">
            How It Works
          </h2>

          <div className="space-y-0">
            {STEPS.map((step, i) => (
              <div key={step.title} className="flex gap-6 items-start pb-10 last:pb-0">
                {/* Step number + connector line */}
                <div className="flex flex-col items-center">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[#2D3561] text-white font-pixel text-xs">
                    {i + 1}
                  </div>
                  {i < STEPS.length - 1 && (
                    <div className="w-px flex-1 bg-[#2D3561]/20 mt-2 min-h-[40px]" />
                  )}
                </div>
                {/* Content */}
                <div className="pt-1.5">
                  <h3 className="font-semibold text-[#2D3561] text-lg mb-1">{step.title}</h3>
                  <p className="text-gray-500 text-base">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 5. vs. Competitors ──────────────────────────────────────────────── */}
      <section className="px-8 py-20" id="compare">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-pixel text-2xl md:text-3xl text-center text-[#2D3561] mb-12">
            Why SOTA StatWorks?
          </h2>

          <div className="overflow-x-auto rounded-2xl border border-gray-100 card-elevated">
            <table className="w-full text-base">
              <thead>
                <tr className="border-b border-gray-100 bg-[#F5F5F7]">
                  <th className="px-6 py-4 text-left font-semibold text-gray-500">Feature</th>
                  <th className="px-6 py-4 text-center font-semibold text-[#FF6B4A]">SOTA StatWorks</th>
                  <th className="px-6 py-4 text-center font-semibold text-gray-400">SPSS</th>
                  <th className="px-6 py-4 text-center font-semibold text-gray-400">SmartPLS</th>
                  <th className="px-6 py-4 text-center font-semibold text-gray-400">Generic AI</th>
                </tr>
              </thead>
              <tbody>
                {COMPARE_ROWS.map((row) => (
                  <tr key={row.feature} className="border-b border-gray-50 last:border-0">
                    <td className="px-6 py-3.5 font-medium text-[#1A1A2E]">{row.feature}</td>
                    <td className="px-6 py-3.5 text-center">{row.sota ? "✅" : "❌"}</td>
                    <td className="px-6 py-3.5 text-center">{row.spss ? "✅" : "❌"}</td>
                    <td className="px-6 py-3.5 text-center">{row.smartpls ? "✅" : "❌"}</td>
                    <td className="px-6 py-3.5 text-center">{row.ai ? "✅" : "❌"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* ── 6. Tech Stack ───────────────────────────────────────────────────── */}
      <section className="px-8 py-20 bg-[#F5F5F7]" id="tech">
        <div className="max-w-5xl mx-auto">
          <h2 className="font-pixel text-2xl md:text-3xl text-center text-[#2D3561] mb-12">
            Built With
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {TECH.map((t) => (
              <div
                key={t.name}
                className="rounded-xl bg-white p-4 text-center card-elevated hover:shadow-md transition-shadow"
              >
                <div className="text-2xl mb-2">{t.icon}</div>
                <div className="font-semibold text-[#2D3561] text-base">{t.name}</div>
                <div className="text-gray-400 text-sm mt-0.5">{t.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── 7. Team ─────────────────────────────────────────────────────────── */}
      <section className="px-8 py-20" id="team">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="font-pixel text-2xl md:text-3xl text-[#2D3561] mb-8">
            Our Team
          </h2>
          {/* Two-logo cluster: Phú Nhuận Builder (left) × SOTA Works (right) */}
          <div className="flex items-center justify-center gap-8 mb-6">
            <Image
              src="/phunhuanbuilder.png"
              alt="Phú Nhuận Builder"
              width={200}
              height={80}
              className="object-contain"
            />
            <span className="text-3xl text-gray-300 font-light">×</span>
            <Image
              src="/sotaworks.png"
              alt="SOTA Works"
              width={160}
              height={60}
              className="object-contain"
            />
          </div>
          <p className="text-xl font-semibold text-[#2D3561] mb-2">
            Phú Nhuận Builder × SOTA Works
          </p>
          <p className="text-gray-500 text-lg">
            Building AI-powered decision tools that make statistics accessible to everyone.
          </p>
        </div>
      </section>

      {/* ── 8. Footer ───────────────────────────────────────────────────────── */}
      <footer className="px-8 py-16 bg-[#2D3561] text-white">
        <div className="max-w-4xl mx-auto text-center">
          <h2 className="font-pixel text-2xl md:text-3xl mb-4">
            Ready to decide?
          </h2>
          <p className="text-white/60 mb-8 max-w-lg mx-auto text-lg">
            From raw data to actionable decisions in under 60 seconds.
            No statistics required.
          </p>
          <Link
            href="/app"
            className="group inline-flex items-center gap-3 rounded-xl bg-[#FF6B4A] px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-black/20 transition-all hover:bg-[#e85d3f] hover:scale-105 active:scale-100"
          >
            🚀 Launch to App
            <span className="transition-transform group-hover:translate-x-1">→</span>
          </Link>
          <p className="mt-12 text-white/30 text-sm">
            SOTA StatWorks — From Data to Decisions, Instantly. © 2026
          </p>
        </div>
      </footer>
    </main>
  );
}

/* ─── Static Data ──────────────────────────────────────────────────────────── */

const PROBLEMS = [
  {
    icon: "🧩",
    title: "Tools Are Too Complex",
    desc: "SPSS and SmartPLS require hours of statistical training before producing any insight. You shouldn't need a PhD to understand your data.",
  },
  {
    icon: "📊",
    title: "Output ≠ Decision",
    desc: "Traditional tools return p-values and coefficient tables. Users cannot translate numbers into business actions without expert help.",
  },
  {
    icon: "🔮",
    title: "No Simulation",
    desc: "No lightweight tool lets a non-expert ask 'What happens if I improve Trust by 20%?' and get an instant, quantified answer.",
  },
];

const SOLUTIONS = [
  {
    icon: "💬",
    title: "Ask Anything",
    desc: "Type a question in plain English — 'What affects retention?' — and get a clear, ranked answer. No configuration, no menus.",
  },
  {
    icon: "🤖",
    title: "Auto Statistical Modeling",
    desc: "AI automatically selects the right model (OLS Regression or PLS-SEM) based on your data structure. You never choose.",
  },
  {
    icon: "🎮",
    title: "Simulate Decisions",
    desc: "Drag a slider to change a variable by ±50%. See the predicted impact on your target outcome instantly — like a decision simulator.",
  },
];

const STEPS = [
  { title: "Upload Your Data", desc: "Drag and drop an Excel or CSV file. Add optional Word/PowerPoint context." },
  { title: "Ask a Question", desc: 'Type a natural-language question like "What drives customer retention?"' },
  { title: "AI Selects the Model", desc: "The system auto-selects OLS Regression or PLS-SEM based on your data structure." },
  { title: "Get Ranked Insights", desc: "See the top drivers, a one-line summary, and an actionable recommendation." },
  { title: "Simulate Changes", desc: "Drag a slider to test 'what-if' scenarios and see predicted impacts in real time." },
];

const COMPARE_ROWS = [
  { feature: "Natural language query",   sota: true,  spss: false, smartpls: false, ai: true },
  { feature: "Real statistical models",  sota: true,  spss: true,  smartpls: true,  ai: false },
  { feature: "Auto model selection",     sota: true,  spss: false, smartpls: false, ai: false },
  { feature: "What-if simulation",       sota: true,  spss: false, smartpls: false, ai: false },
  { feature: "No setup required",        sota: true,  spss: false, smartpls: false, ai: true },
  { feature: "Business-language output",  sota: true,  spss: false, smartpls: false, ai: true },
  { feature: "One-screen interface",     sota: true,  spss: false, smartpls: false, ai: false },
];

const TECH = [
  { icon: "⚡", name: "FastAPI", desc: "Python backend" },
  { icon: "▲", name: "Next.js", desc: "React frontend" },
  { icon: "🧠", name: "GPT-5.4", desc: "AI insight engine" },
  { icon: "📐", name: "NumPy/SciPy", desc: "Statistical core" },
  { icon: "🔐", name: "Clerk", desc: "Authentication" },
  { icon: "🗄️", name: "Supabase", desc: "Metadata DB" },
  { icon: "☁️", name: "Cloudflare R2", desc: "Object storage" },
  { icon: "🚀", name: "Vercel", desc: "Frontend hosting" },
];
