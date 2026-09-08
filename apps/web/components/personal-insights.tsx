"use client";

import Link from "next/link";

import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { useT } from "@/lib/i18n/provider";
import { cn, formatScore } from "@/lib/utils";
import type { KindAccuracy, Progress, ProgressAttempt, QuestionKind, WeakExam } from "@/types/api";

export function PersonalInsights({ progress }: { progress: Progress }) {
  const t = useT();
  const trend = progress.trend ?? [];
  const weak = progress.weak_exams ?? [];
  const kinds = progress.kind_accuracy ?? [];
  if (!trend.length && !weak.length && !kinds.length) {
    return null;
  }

  return (
    <div className="space-y-3">
      <div>
        <h2 className="text-sm font-medium text-muted-foreground">{t("overview.insights")}</h2>
        <p className="mt-1 text-xs text-muted-foreground">{t("overview.insightsHint")}</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        {trend.length ? (
          <Card className="p-5">
            <CardTitle className="text-sm font-medium">{t("overview.trend")}</CardTitle>
            <CardDescription>
              {trend.length < 2 ? t("overview.trendNeedMore") : t("overview.trendHint")}
            </CardDescription>
            <ScoreTrend items={trend} />
          </Card>
        ) : null}
        {trend.length || weak.length ? (
          <Card className="p-5">
            <CardTitle className="text-sm font-medium">{t("overview.reinforce")}</CardTitle>
            <CardDescription>{t("overview.reinforceHint")}</CardDescription>
            {weak.length ? (
              <ul className="mt-4 space-y-2">
                {weak.map((item) => (
                  <WeakExamRow key={item.exam_id} item={item} />
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">{t("overview.reinforceEmpty")}</p>
            )}
          </Card>
        ) : null}
        {kinds.length ? (
          <Card className="p-5">
            <CardTitle className="text-sm font-medium">{t("overview.byKind")}</CardTitle>
            <CardDescription>{t("overview.byKindHint")}</CardDescription>
            <ul className="mt-4 space-y-3">
              {kinds.map((item) => (
                <KindAccuracyRow key={item.kind} item={item} />
              ))}
            </ul>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function ScoreTrend({ items }: { items: ProgressAttempt[] }) {
  const t = useT();
  const last = items[items.length - 1];
  const previous = items.length > 1 ? items[items.length - 2] : null;
  const delta = previous == null ? null : Math.round(last.score - previous.score);
  const summary =
    delta == null
      ? null
      : delta > 0
        ? t("overview.trendUp", { delta })
        : delta < 0
          ? t("overview.trendDown", { delta: Math.abs(delta) })
          : t("overview.trendFlat");

  if (items.length < 2) {
    return (
      <Link
        href={`/exams/${last.exam_id}?attempt=${last.id}`}
        className="mt-4 block rounded-lg border border-transparent px-1 py-1 transition-colors hover:border-accent/35 hover:bg-accent/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <p className="text-3xl font-semibold tracking-tight tabular-nums">{formatScore(last.score)}</p>
        <p className="mt-1 truncate text-sm text-muted-foreground">{last.exam_title}</p>
      </Link>
    );
  }

  return (
    <div className="mt-4 space-y-3">
      {summary ? <p className="text-sm font-medium">{summary}</p> : null}
      <div
        className="flex gap-2"
        role="img"
        aria-label={`${t("overview.trendHint")} ${summary ?? ""}`.trim()}
      >
        <div className="flex h-28 shrink-0 flex-col text-[10px] tabular-nums text-muted-foreground">
          <span className="mb-1 h-4 shrink-0" aria-hidden="true" />
          <div className="flex min-h-0 flex-1 flex-col justify-between">
            <span>{t("overview.trendScaleMax")}</span>
            <span>{t("overview.trendScaleMin")}</span>
          </div>
        </div>
        <div className="flex h-28 min-w-0 flex-1 items-end gap-2 overflow-x-auto">
          {items.map((item) => (
            <Link
              key={item.id}
              href={`/exams/${item.exam_id}?attempt=${item.id}`}
              title={`${item.exam_title} · ${formatScore(item.score)}`}
              className="flex h-full w-10 shrink-0 flex-col items-center focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="mb-1 h-4 text-[11px] font-medium leading-4 tabular-nums text-foreground">
                {Math.round(item.score)}%
              </span>
              <span className="flex min-h-0 w-7 flex-1 items-end">
                <span
                  className={cn(
                    "w-full min-h-1 rounded-t-sm bg-accent",
                    item.score < 50 ? "opacity-40" : item.score < 80 ? "opacity-70" : "opacity-100",
                  )}
                  style={{ height: `${Math.max(4, Math.min(100, item.score))}%` }}
                />
              </span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function WeakExamRow({ item }: { item: WeakExam }) {
  const t = useT();
  const attemptLabel =
    item.attempt_count === 1
      ? t("overview.attemptOnExam", { count: item.attempt_count })
      : t("overview.attemptsOnExam", { count: item.attempt_count });
  return (
    <li>
      <Link
        href={`/exams/${item.exam_id}`}
        className="flex items-center justify-between gap-3 rounded-lg border border-transparent px-2 py-2 transition-colors hover:border-accent/35 hover:bg-accent/15"
      >
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{item.exam_title}</p>
          <p className="text-xs text-muted-foreground">{attemptLabel}</p>
        </div>
        <span className="shrink-0 text-sm font-medium text-accent">{formatScore(item.average_score)}</span>
      </Link>
    </li>
  );
}

function KindAccuracyRow({ item }: { item: KindAccuracy }) {
  const t = useT();
  const percent = item.accuracy ?? 0;
  return (
    <li>
      <div className="flex items-center justify-between gap-3 text-sm">
        <span>{questionKindLabel(item.kind, t)}</span>
        <span className="tabular-nums text-muted-foreground">
          {item.correct}/{item.total} · {formatScore(item.accuracy)}
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
        aria-label={questionKindLabel(item.kind, t)}
      >
        <div className="h-full rounded-full bg-accent" style={{ width: `${Math.max(0, Math.min(100, percent))}%` }} />
      </div>
    </li>
  );
}

function questionKindLabel(kind: QuestionKind | string, t: (key: string) => string) {
  switch (kind) {
    case "true_false":
      return t("exams.trueFalse");
    case "multiple_choice":
      return t("exams.multiCorrect");
    default:
      return t("exams.singleChoice");
  }
}
