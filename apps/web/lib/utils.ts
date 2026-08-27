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

export function formatMoney(amount: number, currency: string, locale: Locale = DEFAULT_LOCALE): string {
  return new Intl.NumberFormat(localeTag(locale), {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amount / 100);
}
