"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "next/navigation";

export function LanguageSwitcher() {
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const switchLocale = (newLocale: string) => {
    // Replace /<currentLocale> prefix with /<newLocale>
    const segments = pathname.split("/");
    if (segments[1] === locale) {
      segments[1] = newLocale;
    } else {
      segments.splice(1, 0, newLocale);
    }
    router.push(segments.join("/") || "/");
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
