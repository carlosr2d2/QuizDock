"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { AttemptRow } from "@/components/attempt-row";
import { DocumentCover } from "@/components/document-cover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle, surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ListLoader, Loader, ProgressBar } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { canCreateContent } from "@/lib/permissions";
import { formatDateTime, formatScore } from "@/lib/utils";
import type { Exam, Progress, User } from "@/types/api";

export default function ExamsPage() {
  const { t, locale } = useI18n();
  const exams = useQuery({
    queryKey: ["exams"],
    queryFn: () => apiFetch<Exam[]>("/api/v1/exams"),
    refetchOnMount: "always",
    refetchInterval: (query) => {
      const items = query.state.data ?? [];
      return items.some((exam) => exam.status === "generating") ? 1000 : false;
    },
  });
  const progress = useQuery({
    queryKey: ["progress"],
    queryFn: () => apiFetch<Progress>("/api/v1/progress"),
    refetchOnMount: "always",
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
  });
  const canAuthor = canCreateContent(me.data);

  const recent = progress.data?.recent ?? [];
  const items = exams.data ?? [];
  const pendingAssigned = items.filter(
    (exam) => exam.assigned_to_me && exam.assignment_status === "pending" && exam.status === "ready",
  );
  const pendingIds = new Set(pendingAssigned.map((exam) => exam.id));
  const catalog = items.filter((exam) => !pendingIds.has(exam.id));

  const hint = exams.data?.some((exam) => exam.can_assign)
    ? t("exams.assignHint")
    : exams.data?.some((exam) => exam.assigned_to_me)
      ? t("exams.assignedHint")
      : canAuthor
        ? t("exams.authorHint")
        : t("exams.memberHint");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("exams.title")}</h1>
        {exams.isLoading ? (
          <Loader label={t("exams.loading")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">{hint}</p>
        )}
      </div>

      {exams.isError ? (
        <ErrorState
          title={t("exams.loadError")}
          error={exams.error}
          onRetry={() => void exams.refetch()}
        />
      ) : exams.isLoading ? (
        <ListLoader label={t("exams.loadingList")} />
      ) : pendingAssigned.length ? (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">{t("exams.companyPending")}</h2>
          <ul className={surfaceListClass}>
            {pendingAssigned.map((exam) => (
              <ExamRow key={exam.id} exam={exam} pending />
            ))}
          </ul>
        </div>
      ) : null}

      {catalog.length ? (
        <ul className={surfaceListClass}>
          {catalog.map((exam) => (
            <ExamRow key={exam.id} exam={exam} />
          ))}
        </ul>
      ) : !exams.isLoading && !exams.isError && !pendingAssigned.length ? (
        <EmptyState
          title={t("exams.emptyTitle")}
          description={canAuthor ? t("exams.emptyAuthor") : t("exams.emptyMember")}
        >
          {canAuthor ? (
            <Link href="/documents">
              <Button variant="outline">{t("overview.goDocuments")}</Button>
            </Link>
          ) : null}
        </EmptyState>
      ) : null}

      {progress.isLoading ? <Loader label={t("exams.loadingHistory")} className="py-4" /> : recent.length ? (
        <Card>
          <CardTitle>{t("exams.history")}</CardTitle>
          <CardDescription>{t("exams.historyBody")}</CardDescription>
          <ul className="mt-4 space-y-1">
            {recent.map((item) => (
              <li key={item.id}>
                <AttemptRow
                  title={item.exam_title}
                  subtitle={formatDateTime(item.completed_at, locale)}
                  score={item.score}
                  href={`/exams/${item.exam_id}?attempt=${item.id}`}
                />
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}

function ExamRow({ exam, pending = false }: { exam: Exam; pending?: boolean }) {
  const { t } = useI18n();
  const assignmentLabel =
    exam.can_assign && exam.assignment_count
      ? t("exams.doneCount", { done: exam.assignment_completed_count, total: exam.assignment_count })
      : exam.assigned_to_me && exam.assignment_status === "completed"
        ? t("exams.done")
        : exam.attempt_count
          ? `${exam.attempt_count} ${exam.attempt_count === 1 ? t("overview.attemptOne") : t("overview.attemptOther")}`
          : t(`status.${exam.status === "archived" ? "archived" : exam.status}`);

  return (
    <li className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="flex min-w-0 items-center gap-4">
        <DocumentCover
          documentId={exam.document_id}
          hasCover={exam.has_cover}
          kind={exam.document_kind}
          title={exam.document_title ?? exam.title}
        />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{exam.title}</p>
          <p className="text-xs text-muted-foreground">
            {exam.kind} · {t("exams.questions", { count: exam.question_count })}
            {exam.error_message ? ` · ${exam.error_message}` : ""}
          </p>
          {exam.status === "ready" ? (
            <p className="mt-1 text-xs">
              {exam.can_assign && exam.assignment_count ? (
                <span className="text-accent">
                  {t("exams.completedOf", {
                    done: exam.assignment_completed_count,
                    total: exam.assignment_count,
                    assignedLabel:
                      exam.assignment_count === 1 ? t("exams.assignedOne") : t("exams.assignedOther"),
                  })}
                </span>
              ) : exam.attempt_count ? (
                <span className="text-accent">
                  {t("exams.lastScore", {
                    score: formatScore(exam.last_score),
                    count: exam.attempt_count,
                    attemptLabel:
                      exam.attempt_count === 1 ? t("overview.attemptOne") : t("overview.attemptOther"),
                  })}
                </span>
              ) : pending ? (
                <span className="text-accent">{t("exams.assignedPendingShort")}</span>
              ) : (
                <span className="text-muted-foreground">{t("exams.notTaken")}</span>
              )}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge
          className={
            pending || (exam.status === "ready" && (exam.attempt_count || exam.assignment_count))
              ? "border-accent/30 bg-accent/10 text-accent"
              : undefined
          }
        >
          {pending ? t("common.pending") : assignmentLabel}
        </Badge>
        {exam.status === "ready" ? (
          <>
            {exam.can_assign ? (
              <Link href={`/exams/${exam.id}`}>
                <Button size="sm" variant="outline">
                  {t("exams.assign")}
                </Button>
              </Link>
            ) : null}
            <Link href={`/exams/${exam.id}`}>
              <Button size="sm">
                {pending
                  ? t("exams.take")
                  : exam.attempt_count
                    ? t("exams.viewHistory")
                    : exam.can_assign
                      ? t("exams.view")
                      : t("exams.take")}
              </Button>
            </Link>
          </>
        ) : exam.status === "generating" ? (
          <ProgressBar
            compact
            className="w-36"
            value={exam.generated_count ?? 0}
            max={exam.question_count || 1}
            label={t("documents.generating")}
          />
        ) : null}
      </div>
    </li>
  );
}
