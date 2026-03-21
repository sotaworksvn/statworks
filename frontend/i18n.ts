import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

export default getRequestConfig(async () => {
  // Read locale from the NEXT_LOCALE cookie set by LanguageSwitcher.
  // Falls back to "vi" (Vietnamese) — the product default.
  const cookieStore = await cookies();
  const raw = cookieStore.get("NEXT_LOCALE")?.value;
  const locale = raw === "en" ? "en" : "vi";

  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
