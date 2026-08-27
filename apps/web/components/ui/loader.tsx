"use client";

import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

export function Spinner({ className }: { className?: string }) {
  return (
    <svg
      className={cn("h-4 w-4 animate-spin", className)}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" />
      <path
        className="opacity-90"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V1C5.373 1 1 5.373 1 12h3zm2 5.291A7.962 7.962 0 014 12H1c0 3.042 1.135 5.824 3 7.938l2-1.647z"
      />
    </svg>
  );
}

export function Loader({
  label,
  className,
}: {
  label?: string;
  className?: string;
}) {
  const t = useT();
  return (
    <div role="status" className={cn("flex items-center gap-2 text-sm text-muted-foreground", className)}>
      <Spinner className="text-accent" />
      <span>{label ?? t("common.loading")}</span>
    </div>
  );
}

export function PageLoader({ label }: { label?: string }) {
  const t = useT();
  return (
    <div className="flex min-h-[36vh] flex-col items-center justify-center gap-3" role="status">
      <Spinner className="h-7 w-7 text-accent" />
      <p className="text-sm text-muted-foreground">{label ?? t("common.loading")}</p>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-muted", className)} aria-hidden="true" />;
}

export function ProgressBar({
  value,
  max,
  label,
  compact = false,
  className,
}: {
  value: number;
  max: number;
  label?: string;
  compact?: boolean;
  className?: string;
}) {
  const t = useT();
  const total = Math.max(max, 1);
  const current = Math.max(0, Math.min(value, total));
  const started = current > 0;
  const percent = started ? Math.round((current / total) * 100) : 0;

  return (
    <div
      className={cn("space-y-2", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={current}
      aria-label={label ?? t("common.progress")}
    >
      {label ? (
        <p className={cn("text-muted-foreground", compact ? "text-xs" : "text-sm")}>{label}</p>
      ) : null}
      <div className={cn("overflow-hidden rounded-full bg-muted", compact ? "h-1.5" : "h-2.5")}>
        {started ? (
          <div
            className="h-full rounded-full bg-accent transition-[width] duration-500 ease-out"
            style={{ width: `${percent}%` }}
          />
        ) : (
          <div className="h-full w-1/3 animate-pulse rounded-full bg-accent/70" />
        )}
      </div>
      <p className={cn("text-muted-foreground", compact ? "text-[11px]" : "text-xs")}>
        {started
          ? t("common.progressValue", { current, total, percent })
          : t("common.preparing")}
      </p>
    </div>
  );
}

export function ListLoader({ rows = 4, label }: { rows?: number; label?: string }) {
  const t = useT();
  const resolved = label ?? t("common.loadingList");
  return (
    <div className="space-y-3" role="status" aria-label={resolved}>
      {Array.from({ length: rows }, (_, index) => (
        <div
          key={index}
          className="flex items-center gap-4 rounded-xl border border-border bg-card px-5 py-4"
        >
          <Skeleton className="h-[5.5rem] w-[4.1rem] shrink-0 rounded-md" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-2/3" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-8 w-20 shrink-0" />
        </div>
      ))}
      <Loader label={resolved} />
    </div>
  );
}
