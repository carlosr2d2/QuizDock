"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";

import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageLoader, Loader } from "@/components/ui/loader";
import { surfaceListClass } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";
import { formatDateTime } from "@/lib/utils";
import type { Appeal } from "@/types/api";

export default function TeamAppealsInboxPage() {
  const { t, locale } = useI18n();
  const { me, team, snapshot, isPersonal } = useTeamPage();
  const canView =
    snapshot?.role === "owner" || snapshot?.role === "admin" || snapshot?.role === "auditor";
  const [status, setStatus] = useState<string>("");

  const appeals = useQuery({
    queryKey: ["appeals", "inbox", status],
    queryFn: () =>
      apiFetch<Appeal[]>(
        `/api/v1/appeals?inbox=true${status ? `&status=${encodeURIComponent(status)}` : ""}`,
      ),
    enabled: Boolean(snapshot) && !isPersonal && canView,
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("appeals.inboxTitle")}</h1>
        {team.isLoading ? (
          <Loader label={t("common.loadingWorkspace")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? t("appeals.inboxPersonal")
              : t("appeals.inboxBody", { name: snapshot?.organization.name ?? t("team.thisWorkspace") })}
          </p>
        )}
      </div>

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel={t("team.goTeam")} /> : null}
      {!isPersonal && snapshot && !canView ? (
        <p className="text-sm text-muted-foreground">{t("appeals.forbidden")}</p>
      ) : null}

      {!isPersonal && canView ? (
        <div className="flex flex-wrap gap-2">
          {[
            { value: "", label: t("appeals.filterAll") },
            { value: "pending", label: t("appeals.filterPending") },
            { value: "in_review", label: t("appeals.status.in_review") },
            { value: "needs_info", label: t("appeals.status.needs_info") },
          ].map((item) => (
            <button
              key={item.value || "all"}
              type="button"
              onClick={() => setStatus(item.value)}
              className={`rounded-md border px-3 py-1.5 text-sm ${
                status === item.value
                  ? "border-accent bg-accent/10 text-foreground"
                  : "border-border text-muted-foreground hover:bg-muted"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}

      {appeals.isLoading ? <PageLoader label={t("appeals.loading")} /> : null}
      {appeals.isError ? (
        <ErrorState
          title={t("appeals.loadError")}
          error={appeals.error}
          onRetry={() => void appeals.refetch()}
        />
      ) : null}

      {appeals.data?.length ? (
        <ul className={surfaceListClass}>
          {appeals.data.map((item) => (
            <li key={item.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-foreground">{item.exam_title}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {t("appeals.student")}: {item.student_name || item.student_email}
                </p>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{item.question_prompt}</p>
                <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(item.created_at, locale)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge>{t(`appeals.status.${item.status}`)}</Badge>
                <Link
                  href={`/team/appeals/${item.id}`}
                  className="text-sm underline-offset-4 hover:underline"
                >
                  {t("appeals.open")}
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : appeals.data ? (
        <EmptyState title={t("appeals.inboxEmpty")} description={t("appeals.inboxEmptyBody")} />
      ) : null}
    </div>
  );
}
