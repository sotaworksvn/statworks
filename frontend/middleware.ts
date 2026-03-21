import createMiddleware from "next-intl/middleware";

export default createMiddleware({
  locales: ["vi", "en"],
  defaultLocale: "vi",
  // "never" = no URL rewriting at all.
  // Locale is read from the NEXT_LOCALE cookie (set by LanguageSwitcher).
  // This means app/page.tsx stays at "/" — no [locale] directory needed.
  localePrefix: "never",
  // Don't auto-detect from Accept-Language header so Vietnamese is always default
  localeDetection: false,
});

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
