import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatScore(score: number | null | undefined): string {
  if (score == null || Number.isNaN(score)) return "—";
  const rounded = Math.round(score * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}%`;
}

export function formatDate(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleDateString("es", { dateStyle: "medium" });
}

export function formatDateTime(value: string | Date): string {
  const date = typeof value === "string" ? new Date(value) : value;
  return date.toLocaleString("es", { dateStyle: "medium", timeStyle: "short" });
}
