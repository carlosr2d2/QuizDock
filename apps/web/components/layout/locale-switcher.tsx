"use client";

import { useI18n } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { Locale } from "@/lib/i18n/config";

export function LocaleSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();

  return (
    <div className={cn("inline-flex rounded-md border border-border p-0.5 text-xs", className)} role="group" aria-label={t("common.language")}>
      {(["es", "en"] as Locale[]).map((item) => (
        <button
          key={item}
          type="button"
          className={cn(
            "rounded px-2 py-1 font-medium",
            locale === item
              ? "bg-accent text-accent-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
          aria-pressed={locale === item}
          onClick={() => setLocale(item)}
        >
          {item.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
