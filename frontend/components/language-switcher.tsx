"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "next/navigation";

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const switchLocale = (newLocale: string) => {
    // With localePrefix: "as-needed":
    //   "vi" (default) → no prefix in URL  e.g. /  or /app/chat
    //   "en"           → /en prefix        e.g. /en or /en/app/chat
    //
    // Strategy: strip any known locale prefix, then re-add the target prefix.
    const stripped = pathname.replace(/^\/(vi|en)(?=\/|$)/, "") || "/";

    if (newLocale === "vi") {
      // Default locale — no prefix needed
      router.push(stripped);
    } else {
      // Non-default — add /en prefix
      router.push(`/${newLocale}${stripped === "/" ? "" : stripped}`);
    }
  };

  return (
    <div className="flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 p-1">
      <button
        onClick={() => switchLocale("vi")}
        className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
          locale === "vi"
            ? "bg-[#2D3561] text-white shadow-sm"
            : "text-gray-500 hover:text-gray-700"
        }`}
      >
        VI
      </button>
      <button
        onClick={() => switchLocale("en")}
        className={`px-2.5 py-1 rounded-md text-xs font-semibold transition-colors ${
          locale === "en"
            ? "bg-[#2D3561] text-white shadow-sm"
            : "text-gray-500 hover:text-gray-700"
        }`}
      >
        EN
      </button>
    </div>
  );
}
