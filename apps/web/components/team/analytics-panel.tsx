"use client";

import Link from "next/link";
import { useState } from "react";

import { AttemptRow } from "@/components/attempt-row";
import { MemberProgressPanel } from "@/components/member-progress-panel";
import { Card, CardDescription, CardTitle, surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { useI18n } from "@/lib/i18n/provider";
import { formatDateTime, formatScore } from "@/lib/utils";
import type { MembershipRole, TeamAnalytics, TeamMember, TeamMemberAnalytics } from "@/types/api";

export function TeamAnalyticsPanel({ data }: { data: TeamAnalytics }) {
  const { t, locale } = useI18n();
  const [selected, setSelected] = useState<TeamMember | null>(null);

  function openMember(item: TeamMemberAnalytics) {
    setSelected({
      id: item.user_id,
      user_id: item.user_id,
      email: item.email,
      full_name: item.full_name,
      role: item.role as MembershipRole,
    });
  }

  return (
    <div className="space-y-8">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat title={t("team.kpiMembers")} value={data.member_count} />
        <Stat
          title={t("team.kpiCompleted")}
          value={formatScore(data.completion_rate)}
          hint={t("team.ofAssignments", { done: data.completed_count, total: data.assigned_count })}
        />
        <Stat
          title={t("team.kpiAverage")}
          value={formatScore(data.average_score)}
          hint={data.attempt_count ? t("team.attemptsHint", { count: data.attempt_count }) : t("team.noAttempts")}
        />
        <Stat title={t("team.kpiPending")} value={data.pending_count} />
      </div>

      <section>
        <h2 className="text-base font-semibold tracking-tight">{t("team.byMember")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("team.byMemberHint")}</p>
        {data.members.length ? (
          <ul className={`${surfaceListClass} mt-3`}>
            {data.members.map((item) => (
              <li key={item.user_id}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => openMember(item)}
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.full_name}</p>
                    <p className="text-xs text-muted-foreground">
                      {t(`role.${item.role}`)} · {t("team.takenCount", { count: item.exams_taken })}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-4 text-sm">
                    <span className="text-muted-foreground">
                      {t("team.pendingShort", { count: item.assigned_pending_count })}
                    </span>
                    <span className="font-medium">{formatScore(item.average_score)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState className="mt-3 py-10" title={t("team.emptyMembers")} description={t("team.emptyMembersBody")} />
        )}
      </section>

      <section>
        <h2 className="text-base font-semibold tracking-tight">{t("team.byExam")}</h2>
        <p className="mt-1 text-sm text-muted-foreground">{t("team.byExamHint")}</p>
        {data.exams.length ? (
          <ul className={`${surfaceListClass} mt-3`}>
            {data.exams.map((item) => (
              <li key={item.exam_id}>
                <Link
                  href={`/exams/${item.exam_id}`}
                  className="flex items-center justify-between gap-4 px-5 py-4 transition-colors hover:bg-muted/70"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {t("team.completedOf", { done: item.completed_count, total: item.assigned_count })}
                    </p>
                  </div>
                  <span className="shrink-0 text-sm font-medium">{formatScore(item.average_score)}</span>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">{t("team.noAssignedExams")}</p>
        )}
      </section>

      <Card>
        <CardTitle>{t("team.recent")}</CardTitle>
        <CardDescription>{t("team.recentBody")}</CardDescription>
        {data.recent.length ? (
          <ul className="mt-4 space-y-1">
            {data.recent.map((item) => (
              <li key={item.id}>
                <AttemptRow
                  title={item.exam_title}
                  subtitle={`${item.full_name} · ${formatDateTime(item.completed_at, locale)}`}
                  score={item.score}
                  href={`/exams/${item.exam_id}?attempt=${item.id}`}
                />
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">{t("team.noRecent")}</p>
        )}
      </Card>

      {selected ? <MemberProgressPanel member={selected} onClose={() => setSelected(null)} /> : null}
    </div>
  );
}

function Stat({ title, value, hint }: { title: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card px-4 py-3 shadow-sm">
      <p className="text-xs text-muted-foreground">{title}</p>
      <p className="mt-1 text-lg font-semibold tracking-tight">{value}</p>
      {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}
