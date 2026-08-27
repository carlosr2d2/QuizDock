export const LOCALES = ["es", "en"] as const;
export type Locale = (typeof LOCALES)[number];

export const DEFAULT_LOCALE: Locale = "es";
export const LOCALE_STORAGE_KEY = "qd_locale";
export const LOCALE_COOKIE = "qd_locale";

export function parseLocale(value: string | null | undefined): Locale {
  return value === "en" || value === "es" ? value : DEFAULT_LOCALE;
}

export function localeTag(locale: Locale): string {
  return locale === "en" ? "en-US" : "es";
}

type Nested = { [key: string]: string | Nested };

export function translate(messages: Nested, key: string, vars?: Record<string, string | number>): string {
  const parts = key.split(".");
  let current: string | Nested = messages;
  for (const part of parts) {
    if (typeof current !== "object" || current[part] === undefined) return key;
    current = current[part];
  }
  if (typeof current !== "string") return key;
  if (!vars) return current;
  return current.replace(/\{(\w+)\}/g, (_, name: string) =>
    vars[name] === undefined ? `{${name}}` : String(vars[name]),
  );
}
