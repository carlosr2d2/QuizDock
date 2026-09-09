"use client";

import { MembersList } from "@/components/team/members-list";
import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { useT } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";

export default function TeamMembersPage() {
  const t = useT();
  const { me, team, snapshot, isPersonal } = useTeamPage();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("team.membersTitle")}</h1>
        {team.isLoading ? (
          <Loader label={t("common.loadingWorkspace")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? t("team.membersPersonal")
              : t("team.membersBody", { name: snapshot?.organization.name ?? t("team.thisWorkspace") })}
            {!isPersonal && snapshot?.seat_limit != null
              ? ` · ${t("team.seatsUsed", { used: snapshot.seat_used ?? snapshot.members.length, limit: snapshot.seat_limit })}`
              : null}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label={t("team.loadingMembers")} /> : null}
      {team.isError ? (
        <ErrorState
          title={t("team.loadTeamError")}
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel={t("team.viewMembers")} /> : null}
      {!isPersonal && snapshot ? (
        <MembersList snapshot={snapshot} currentUserId={me.data?.id} />
      ) : null}
    </div>
  );
}
