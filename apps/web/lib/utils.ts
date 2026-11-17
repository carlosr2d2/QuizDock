import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

import { DEFAULT_LOCALE, localeTag, type Locale } from "@/lib/i18n/config";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "—";
  const rounded = Math.round(score * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}%`;
}

export function formatDate(value: string | Date, locale: Locale = DEFAULT_LOCALE): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleDateString(localeTag(locale), { dateStyle: "medium" });
}

export function formatDateTime(value: string | Date, locale: Locale = DEFAULT_LOCALE): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleString(localeTag(locale), { dateStyle: "medium", timeStyle: "short" });
}

export function formatRelativeTime(
  value: string | Date,
  locale: Locale = DEFAULT_LOCALE,
): string | null {
  const date = typeof value === "string" ? new Date(value) : value;
  const diffMs = date.getTime() - Date.now();
  if (Number.isNaN(diffMs)) return null;
  const absSec = Math.abs(Math.round(diffMs / 1000));
  if (absSec < 60) return null;
  const rtf = new Intl.RelativeTimeFormat(localeTag(locale), { numeric: "auto" });
  if (absSec < 3600) return rtf.format(Math.round(diffMs / 60_000), "minute");
  if (absSec < 86_400) return rtf.format(Math.round(diffMs / 3_600_000), "hour");
  if (absSec < 86_400 * 7) return rtf.format(Math.round(diffMs / 86_400_000), "day");
  return formatDateTime(date, locale);
}

export function formatMoney(amount: number, currency: string, locale: Locale = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(localeTag(locale), {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amount / 100);
}
