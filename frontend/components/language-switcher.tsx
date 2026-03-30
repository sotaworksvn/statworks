"use client";

import { useLocale } from "next-intl";

export function LanguageSwitcher() {
  const locale = useLocale();

  const switchLocale = (newLocale: string) => {
    if (newLocale === locale) return;
    // Set NEXT_LOCALE cookie and reload so the server picks it up.
    // localePrefix: "never" means the URL never changes — only the cookie.
    document.cookie = `NEXT_LOCALE=${newLocale}; path=/; max-age=31536000; SameSite=Lax`;
    window.location.reload();
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
