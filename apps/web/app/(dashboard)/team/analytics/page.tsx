"use client";

import { useQuery } from "@tanstack/react-query";

import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { TeamAnalyticsPanel } from "@/components/team/analytics-panel";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";
import type { TeamAnalytics } from "@/types/api";

export default function TeamAnalyticsPage() {
  const t = useT();
  const { me, team, snapshot, isPersonal } = useTeamPage();
  const canView =
    snapshot?.role === "owner" || snapshot?.role === "admin" || snapshot?.role === "auditor";
  const analytics = useQuery({
    queryKey: ["team-analytics"],
    queryFn: () => apiFetch<TeamAnalytics>("/api/v1/organizations/current/analytics"),
    enabled: Boolean(snapshot) && !isPersonal && canView,
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("team.analyticsTitle")}</h1>
        {team.isLoading ? (
          <Loader label={t("common.loadingWorkspace")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? t("team.analyticsPersonal")
              : t("team.analyticsBody", { name: snapshot?.organization.name ?? t("team.thisWorkspace") })}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label={t("team.loadingAnalytics")} /> : null}
      {team.isError ? (
        <ErrorState
          title={t("team.loadTeamError")}
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel={t("team.goAnalytics")} /> : null}
      {!isPersonal && snapshot && !canView ? (
        <p className="text-sm text-muted-foreground">{t("team.analyticsForbidden")}</p>
      ) : null}
      {analytics.isLoading ? <PageLoader label={t("team.calculating")} /> : null}
      {analytics.isError ? (
        <ErrorState
          title={t("team.analyticsError")}
          error={analytics.error}
          onRetry={() => void analytics.refetch()}
        />
      ) : null}
      {analytics.data ? <TeamAnalyticsPanel data={analytics.data} /> : null}
    </div>
  );
}
