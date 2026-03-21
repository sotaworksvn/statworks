import Image from "next/image";
import Link from "next/link";
import { LanguageSwitcher } from "@/components/language-switcher";
import { getTranslations } from "next-intl/server";

/* ─── Landing Page (EdTech Track — ETEST sponsored) ────────────────────────── */

export default async function LandingPage() {
  const t = await getTranslations();

  return (
    <main className="min-h-screen bg-white">
      {/* ── Navbar ─────────────────────────────────────────────────────── */}
      <nav className="sticky top-0 z-50 flex items-center justify-between px-6 md:px-10 py-4 bg-white/90 backdrop-blur-md border-b border-gray-100">
        <div className="flex items-center gap-3">
          <Image
            src="/logo.png"
            alt="SOTA StatWorks"
            width={160}
            height={44}
            priority
            className="object-contain"
          />
        </div>
        <div className="flex items-center gap-3">
          <LanguageSwitcher />
          <Link
            href="/app"
            className="rounded-lg bg-[#2D3561] px-5 py-2 text-sm font-semibold text-white hover:bg-[#3a4578] transition-colors"
          >
            {t("common.launchApp")}
          </Link>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="relative flex flex-col items-center justify-center px-6 md:px-10 py-24 md:py-32 text-center overflow-hidden">
        {/* Background blobs */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/4 -top-10 h-[500px] w-[700px] rounded-full bg-[#FFD700]/10 blur-[120px]" />
          <div className="absolute right-1/4 top-1/3 h-[400px] w-[600px] rounded-full bg-[#E84393]/8 blur-[100px]" />
          <div className="absolute left-1/2 bottom-0 h-[300px] w-[500px] -translate-x-1/2 rounded-full bg-[#2D3561]/6 blur-[90px]" />
        </div>

        <div className="relative z-10 flex flex-col items-center gap-6 max-w-4xl mx-auto">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-[#2D3561]/20 bg-[#2D3561]/5 px-4 py-1.5 text-sm text-[#2D3561] font-medium">
            <span className="h-2 w-2 rounded-full bg-[#22C55E] animate-pulse" />
            {t("landing.badge")}
          </div>

          {/* Headline */}
          <h1 className="text-4xl md:text-5xl lg:text-6xl leading-tight tracking-tight font-bold" style={{ fontFamily: "var(--font-inter), system-ui, sans-serif" }}>
            <span className="text-[#FF6B4A]">{t("landing.heroTitle1")}</span>
            <br />
            <span className="text-[#1A1A2E]">{t("landing.heroTitle2")}</span>
          </h1>

          {/* Sub */}
          <p className="text-lg md:text-xl text-gray-500 max-w-2xl leading-relaxed">
            {t("landing.heroSubtitle")}
          </p>

          {/* CTA */}
          <Link
            href="/app"
            className="group mt-2 inline-flex items-center gap-3 rounded-xl bg-[#FF6B4A] px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-[#FF6B4A]/25 transition-all hover:bg-[#e85d3f] hover:shadow-[#FF6B4A]/40 hover:scale-105"
          >
            🚀 {t("common.launchApp")}
            <span className="transition-transform group-hover:translate-x-1">→</span>
          </Link>

          {/* Social proof */}
          <p className="text-sm text-gray-400">
            ✨ {t("common.free")} • Không cần đăng ký • Kết quả trong 60 giây
          </p>
        </div>
      </section>

      {/* ── Problem ────────────────────────────────────────────────────── */}
      <section className="px-6 md:px-10 py-20 bg-[#F5F5F7]" id="problem">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-2xl md:text-3xl text-center text-[#2D3561] mb-3 font-bold">
            {t("landing.problemTitle")}
          </h2>
          <p className="text-center text-gray-500 mb-12 max-w-2xl mx-auto text-base md:text-lg">
            {t("landing.problemSubtitle")}
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {(["blind", "expensive", "noTool"] as const).map((key) => {
              const icons: Record<string, string> = { blind: "🎯", expensive: "💰", noTool: "❓" };
              return (
                <div key={key} className="rounded-2xl bg-white p-8 shadow-sm hover:shadow-md transition-shadow">
                  <div className="text-4xl mb-4">{icons[key]}</div>
                  <h3 className="font-semibold text-[#2D3561] text-xl mb-3">
                    {t(`landing.problems.${key}.title`)}
                  </h3>
                  <p className="text-gray-500 text-base leading-relaxed">
                    {t(`landing.problems.${key}.desc`)}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── Solution ───────────────────────────────────────────────────── */}
      <section className="px-6 md:px-10 py-20" id="solution">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-2xl md:text-3xl text-center text-[#2D3561] mb-3 font-bold">
            {t("landing.solutionTitle")}
          </h2>
          <p className="text-center text-gray-500 mb-12 max-w-2xl mx-auto text-base md:text-lg">
            {t("landing.solutionSubtitle")}
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
            {(["upload", "research", "predict", "simulate"] as const).map((key) => {
              const icons: Record<string, string> = { upload: "📤", research: "🔍", predict: "📊", simulate: "🎮" };
              const colors: Record<string, string> = {
                upload: "bg-blue-50 text-blue-600",
                research: "bg-purple-50 text-purple-600",
                predict: "bg-orange-50 text-orange-600",
                simulate: "bg-green-50 text-green-600",
              };
              return (
                <div
                  key={key}
                  className="rounded-2xl border border-gray-100 bg-white p-6 hover:border-[#FF6B4A]/30 hover:shadow-lg transition-all group"
                >
                  <div className={`mb-4 flex h-12 w-12 items-center justify-center rounded-xl text-2xl ${colors[key]}`}>
                    {icons[key]}
                  </div>
                  <h3 className="font-semibold text-[#2D3561] text-base mb-2 group-hover:text-[#FF6B4A] transition-colors">
                    {t(`landing.solutions.${key}.title`)}
                  </h3>
                  <p className="text-gray-500 text-sm leading-relaxed">
                    {t(`landing.solutions.${key}.desc`)}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ── How It Works ───────────────────────────────────────────────── */}
      <section className="px-6 md:px-10 py-20 bg-[#F5F5F7]" id="how">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl md:text-3xl text-center text-[#2D3561] mb-12 font-bold">
            {t("landing.howItWorksTitle")}
          </h2>

          <div className="space-y-0">
            {(["upload", "auto", "result", "simulate", "apply"] as const).map((key, i) => (
              <div key={key} className="flex gap-5 items-start pb-10 last:pb-0">
                <div className="flex flex-col items-center shrink-0">
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#2D3561] text-white font-bold text-sm">
                    {i + 1}
                  </div>
                  {i < 4 && <div className="w-0.5 flex-1 bg-[#2D3561]/20 mt-2 min-h-[40px]" />}
                </div>
                <div className="pt-1.5 pb-2">
                  <h3 className="font-semibold text-[#2D3561] text-base mb-1">
                    {t(`landing.steps.${key}`)}
                  </h3>
                  <p className="text-gray-500 text-sm leading-relaxed">
                    {t(`landing.steps.${key}Desc`)}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Compare ────────────────────────────────────────────────────── */}
      <section className="px-6 md:px-10 py-20" id="compare">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-2xl md:text-3xl text-center text-[#2D3561] mb-12 font-bold">
            {t("landing.compareTitle")}
          </h2>

          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {(["scholarship", "realtime", "profile", "science", "vietnam", "free"] as const).map((key) => (
              <div key={key} className="rounded-xl border border-gray-100 bg-white p-5 text-center hover:border-[#22C55E]/50 hover:shadow-sm transition-all">
                <div className="text-3xl mb-2">✅</div>
                <div className="font-medium text-[#2D3561] text-sm">
                  {t(`landing.compare.${key}`)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Team ───────────────────────────────────────────────────────── */}
      <section className="px-6 md:px-10 py-20 bg-[#F5F5F7]" id="team">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-2xl md:text-3xl text-[#2D3561] mb-8 font-bold">
            {t("landing.teamTitle")}
          </h2>
          <div className="flex items-center justify-center gap-8 mb-6 flex-wrap">
            <Image
              src="/phunhuanbuilder.png"
              alt="Phú Nhuận Builder"
              width={180}
              height={70}
              className="object-contain opacity-90"
            />
            <span className="text-3xl text-gray-300 font-light">×</span>
            <Image
              src="/sotaworks.png"
              alt="SOTA Works"
              width={140}
              height={55}
              className="object-contain opacity-90"
            />
          </div>
          <p className="text-gray-500 text-base leading-relaxed">
            {t("landing.teamDesc")}
          </p>
        </div>
      </section>

      {/* ── Footer CTA ─────────────────────────────────────────────────── */}
      <footer className="px-6 md:px-10 py-16 bg-[#2D3561] text-white">
        <div className="max-w-3xl mx-auto text-center">
          <h2 className="text-2xl md:text-3xl mb-4 font-bold">
            {t("landing.ctaTitle")}
          </h2>
          <p className="text-white/60 mb-8 max-w-md mx-auto text-base">
            {t("landing.ctaSubtitle")}
          </p>
          <Link
            href="/app"
            className="group inline-flex items-center gap-3 rounded-xl bg-[#FF6B4A] px-8 py-4 text-lg font-semibold text-white shadow-lg shadow-black/20 transition-all hover:bg-[#e85d3f] hover:scale-105"
          >
            🚀 {t("common.launchApp")}
            <span className="transition-transform group-hover:translate-x-1">→</span>
          </Link>
          <p className="mt-12 text-white/30 text-xs">
            {t("landing.footer")}
          </p>
        </div>
      </footer>
    </main>
  );
}
