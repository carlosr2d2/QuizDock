"use client";

import { useQuery } from "@tanstack/react-query";

import { CreateWorkspaceCard } from "@/components/team/create-workspace-card";
import { IncomingInvites } from "@/components/team/incoming-invites";
import { InviteCard } from "@/components/team/invite-card";
import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";
import type { MyInvitation } from "@/types/api";

export default function TeamInvitePage() {
  const t = useT();
  const { me, team, snapshot, isPersonal } = useTeamPage();
  const mine = useQuery({
    queryKey: ["my-invitations"],
    queryFn: () => apiFetch<MyInvitation[]>("/api/v1/invitations"),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("team.inviteTitle")}</h1>
        {team.isLoading ? (
          <Loader label={t("common.loadingWorkspace")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? t("team.invitePersonal")
              : t("team.inviteBody", { name: snapshot?.organization.name ?? t("team.thisWorkspace") })}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label={t("team.loadingInvites")} /> : null}
      {team.isError ? (
        <ErrorState
          title={t("team.loadTeamError")}
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      <IncomingInvites items={mine.data} loading={mine.isLoading} />
      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel={t("team.goInvite")} /> : null}
      {!isPersonal && snapshot ? <InviteCard snapshot={snapshot} /> : null}
      <CreateWorkspaceCard redirectTo="/team/invite" />
    </div>
  );
}
