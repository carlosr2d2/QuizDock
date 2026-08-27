"use client";

import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { useEffect } from "react";

import { AttemptRow } from "@/components/attempt-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CardDescription, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Loader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { formatDateTime, formatScore } from "@/lib/utils";
import type { MemberProgress, TeamMember } from "@/types/api";

export function MemberProgressPanel({
  member,
  onClose,
}: {
  member: TeamMember;
  onClose: () => void;
}) {
  const { t, locale } = useI18n();
  const progress = useQuery({
    queryKey: ["member-progress", member.user_id],
    queryFn: () =>
      apiFetch<MemberProgress>(`/api/v1/organizations/current/members/${member.user_id}/progress`),
  });

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [onClose]);

  const data = progress.data;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center">
      <button
        type="button"
        className="absolute inset-0 bg-foreground/40"
        aria-label={t("team.closeSummary")}
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="member-progress-title"
        className="relative z-10 flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-t-2xl border border-border bg-card shadow-lg sm:rounded-2xl"
      >
        <div className="flex items-start justify-between gap-3 border-b border-border px-5 py-4">
          <div className="min-w-0">
            <CardTitle id="member-progress-title">{member.full_name}</CardTitle>
            <CardDescription>
              {member.email} · {t(`role.${member.role}`)}
            </CardDescription>
          </div>
          <Button type="button" size="sm" variant="ghost" onClick={onClose} aria-label={t("common.close")}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="overflow-y-auto px-5 py-4">
          {progress.isLoading ? <Loader label={t("team.loadingExams")} /> : null}
          {progress.isError ? (
            <ErrorState
              title={t("team.progressError")}
              error={progress.error}
              onRetry={() => void progress.refetch()}
            />
          ) : null}
          {data ? (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <MiniStat title={t("team.taken")} value={data.exams_taken} />
                <MiniStat title={t("team.kpiAverage")} value={formatScore(data.average_score)} />
                <MiniStat title={t("team.bestScore")} value={formatScore(data.best_score)} />
                <MiniStat title={t("team.kpiPending")} value={data.assigned_pending_count} />
              </div>
              {data.recent.length ? (
                <div>
                  <h3 className="text-sm font-medium">{t("team.takenExams")}</h3>
                  <ul className="mt-2 space-y-1">
                    {data.recent.map((item) => (
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
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">{t("team.noMemberExams")}</p>
              )}
              {data.assignments.some((item) => item.status !== "completed") ? (
                <div>
                  <h3 className="text-sm font-medium">{t("team.assignedPending")}</h3>
                  <ul className="mt-2 space-y-2">
                    {data.assignments
                      .filter((item) => item.status !== "completed")
                      .map((item) => (
                        <li
                          key={item.exam_id}
                          className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3"
                        >
                          <p className="truncate text-sm font-medium">{item.exam_title}</p>
                          <Badge>{t("common.pending")}</Badge>
                        </li>
                      ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function MiniStat({ title, value }: { title: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-muted/40 px-4 py-3">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-lg font-semibold tracking-tight">{value}</p>
    </div>
  );
}
