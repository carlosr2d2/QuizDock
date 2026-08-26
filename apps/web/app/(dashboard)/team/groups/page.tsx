"use client";

import { GroupsCard } from "@/components/groups-card";
import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { useTeamPage } from "@/lib/use-team-page";

export default function TeamGroupsPage() {
  const { me, team, snapshot, isPersonal } = useTeamPage();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Grupos</h1>
        {team.isLoading ? (
          <Loader label="Cargando workspace…" className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? "Los grupos solo existen en un equipo de empresa."
              : "Asigna un examen a varios integrantes a la vez. Una persona puede estar en varios grupos."}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label="Cargando grupos…" /> : null}
      {team.isError ? (
        <ErrorState
          title="No se pudieron cargar los grupos"
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel="Ver grupos" /> : null}
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
