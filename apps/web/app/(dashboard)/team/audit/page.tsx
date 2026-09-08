"use client";

import { useQuery } from "@tanstack/react-query";

import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { surfaceListClass } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";
import { formatDateTime } from "@/lib/utils";
import type { Locale } from "@/lib/i18n/config";
import type { AuditEvent, AuditEventList } from "@/types/api";

const PAGE_SIZE = 50;

export default function TeamAuditPage() {
  const { t, locale } = useI18n();
  const { me, team, snapshot, isPersonal } = useTeamPage();
  const canView =
    snapshot?.role === "owner" || snapshot?.role === "admin" || snapshot?.role === "auditor";
  const log = useQuery({
    queryKey: ["team-audit"],
    queryFn: () =>
      apiFetch<AuditEventList>(`/api/v1/organizations/current/audit?limit=${PAGE_SIZE}&offset=0`),
    enabled: Boolean(snapshot) && !isPersonal && canView,
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("team.auditTitle")}</h1>
        {team.isLoading ? (
          <Loader label={t("common.loadingWorkspace")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? t("team.auditPersonal")
              : t("team.auditBody", { name: snapshot?.organization.name ?? t("team.thisWorkspace") })}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label={t("team.loadingAudit")} /> : null}
      {team.isError ? (
        <ErrorState
          title={t("team.loadTeamError")}
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel={t("team.goTeam")} /> : null}
      {!isPersonal && snapshot && !canView ? (
        <p className="text-sm text-muted-foreground">{t("team.auditForbidden")}</p>
      ) : null}
      {log.isLoading ? <PageLoader label={t("team.loadingAudit")} /> : null}
      {log.isError ? (
        <ErrorState
          title={t("team.auditError")}
          error={log.error}
          onRetry={() => void log.refetch()}
        />
      ) : null}
      {log.data?.items.length ? (
        <AuditList items={log.data.items} locale={locale} />
      ) : log.data ? (
        <EmptyState title={t("team.auditEmpty")} description={t("team.auditEmptyBody")} />
      ) : null}
    </div>
  );
}

function AuditList({ items, locale }: { items: AuditEvent[]; locale: Locale }) {
  const { t } = useI18n();
  return (
    <ul className={surfaceListClass}>
      {items.map((item) => (
        <li key={item.id} className="flex flex-col gap-1 px-5 py-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
          <div className="min-w-0">
            <p className="text-sm font-medium">{actionLabel(item.action, t)}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">{item.summary}</p>
          </div>
          <div className="shrink-0 text-xs text-muted-foreground sm:text-right">
            <p>{item.actor_full_name || item.actor_email || t("team.auditSystem")}</p>
            <p className="mt-0.5">{formatDateTime(item.created_at, locale)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function actionLabel(action: string, t: (key: string) => string) {
  const key = `auditAction.${action}`;
  const label = t(key);
  return label === key ? action : label;
}
