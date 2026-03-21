import createMiddleware from "next-intl/middleware";

export default createMiddleware({
  locales: ["vi", "en"],
  defaultLocale: "vi",
  // "as-needed": default locale (vi) has NO prefix → serves at /
  // English gets prefix → /en, /en/app, etc.
  // This means / → Vietnamese (no redirect to /vi → no 404)
  localePrefix: "as-needed",
});

export const config = {
  matcher: ["/((?!api|_next|_vercel|.*\\..*).*)"],
};
