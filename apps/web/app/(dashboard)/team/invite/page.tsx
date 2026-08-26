"use client";

import { useQuery } from "@tanstack/react-query";

import { CreateWorkspaceCard } from "@/components/team/create-workspace-card";
import { IncomingInvites } from "@/components/team/incoming-invites";
import { InviteCard } from "@/components/team/invite-card";
import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useTeamPage } from "@/lib/use-team-page";
import type { MyInvitation } from "@/types/api";

export default function TeamInvitePage() {
  const { me, team, snapshot, isPersonal } = useTeamPage();
  const mine = useQuery({
    queryKey: ["my-invitations"],
    queryFn: () => apiFetch<MyInvitation[]>("/api/v1/invitations"),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Invitar</h1>
        {team.isLoading ? (
          <Loader label="Cargando workspace…" className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? "Las invitaciones se envían desde un equipo de empresa."
              : `Invita a ${snapshot?.organization.name ?? "este workspace"} por correo.`}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label="Cargando invitaciones…" /> : null}
      {team.isError ? (
        <ErrorState
          title="No se pudo cargar el equipo"
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      <IncomingInvites items={mine.data} loading={mine.isLoading} />
      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel="Ir e invitar" /> : null}
      {!isPersonal && snapshot ? <InviteCard snapshot={snapshot} /> : null}
      <CreateWorkspaceCard redirectTo="/team/invite" />
    </div>
  );
}
