"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { ReactNode } from "react";

import { useT } from "@/lib/i18n/provider";
import { cn, formatScore } from "@/lib/utils";

type AttemptRowProps = {
  title: string;
  subtitle: string;
  score: number;
  active?: boolean;
  actionLabel?: string;
  href?: string;
  onClick?: () => void;
};

export function AttemptRow({
  title,
  subtitle,
  score,
  active = false,
  actionLabel,
  href,
  onClick,
}: AttemptRowProps) {
  const t = useT();
  const label = active ? t("common.viewing") : (actionLabel ?? t("common.viewResult"));
  const content = (
    <>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>
      </div>
      <span className="shrink-0 rounded-full bg-accent/15 px-2.5 py-1 text-sm font-medium text-accent">
        {formatScore(score)}
      </span>
      <span
        className={cn(
          "hidden shrink-0 items-center gap-1 rounded-md px-3 py-1.5 text-sm font-medium sm:inline-flex",
          active ? "bg-accent text-accent-foreground" : "border border-accent/50 bg-background text-accent",
        )}
      >
        {label}
        <ChevronRight className="h-3.5 w-3.5" />
      </span>
      <ChevronRight className="h-4 w-4 shrink-0 text-accent sm:hidden" />
    </>
  );

  const className = cn(
    "flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left transition-colors",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    active
      ? "border-accent/40 bg-accent/15"
      : "border-transparent hover:border-accent/35 hover:bg-accent/15",
  );

  if (href) {
    return (
      <Link href={href} className={className}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={className} aria-current={active ? "true" : undefined}>
      {content}
    </button>
  );
}

export function AttemptHistoryCard({
  title,
  description,
  children,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
}) {
  const t = useT();
  return (
    <section className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <h2 className="text-sm font-medium">{title ?? t("exams.history")}</h2>
      {description ? <p className="mt-1 text-xs text-muted-foreground">{description}</p> : null}
      <ul className="mt-3 space-y-1">{children}</ul>
    </section>
  );
}
