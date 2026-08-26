"use client";

import { MembersList } from "@/components/team/members-list";
import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { useTeamPage } from "@/lib/use-team-page";

export default function TeamMembersPage() {
  const { me, team, snapshot, isPersonal } = useTeamPage();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Miembros</h1>
        {team.isLoading ? (
          <Loader label="Cargando workspace…" className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? "La lista de miembros está en un equipo de empresa."
              : `Quién forma parte de ${snapshot?.organization.name ?? "este workspace"}.`}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label="Cargando miembros…" /> : null}
      {team.isError ? (
        <ErrorState
          title="No se pudo cargar el equipo"
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel="Ver miembros" /> : null}
      {!isPersonal && snapshot ? (
        <MembersList snapshot={snapshot} currentUserId={me.data?.id} />
      ) : null}
    </div>
  );
}
