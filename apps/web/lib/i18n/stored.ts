import { LOCALE_STORAGE_KEY, parseLocale, translate } from "./config";
import { en, es } from "./messages";

export function tStored(key: string, vars?: Record<string, string | number>): string {
  const raw = typeof window === "undefined" ? null : localStorage.getItem(LOCALE_STORAGE_KEY);
  const locale = parseLocale(raw);
  return translate((locale === "en" ? en : es) as never, key, vars);
}
