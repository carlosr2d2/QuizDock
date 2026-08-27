"use client";

import { GroupsCard } from "@/components/groups-card";
import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { useT } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";

export default function TeamGroupsPage() {
  const t = useT();
  const { me, team, snapshot, isPersonal } = useTeamPage();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("team.groupsTitle")}</h1>
        {team.isLoading ? (
          <Loader label={t("common.loadingWorkspace")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal ? t("team.groupsPersonal") : t("team.groupsPageBody")}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label={t("team.loadingGroups")} /> : null}
      {team.isError ? (
        <ErrorState
          title={t("team.loadGroupsError")}
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel={t("team.viewGroups")} /> : null}
      {!isPersonal && snapshot ? (
        <GroupsCard
          groups={snapshot.groups ?? []}
          members={snapshot.members}
          canManage={snapshot.can_manage}
        />
      ) : null}
    </div>
  );
}
