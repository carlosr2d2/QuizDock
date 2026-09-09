"use client";

import { CreateWorkspaceCard } from "@/components/team/create-workspace-card";
import { Loader } from "@/components/ui/loader";
import { useT } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";

export default function NewWorkspacePage() {
  const t = useT();
  const { team, snapshot, isPersonal } = useTeamPage();

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("team.createWorkspace")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("team.newTeamSwitch")}</p>
      </div>

      {team.isLoading ? <Loader label={t("common.loadingWorkspace")} /> : null}

      {!team.isLoading && !isPersonal && snapshot ? (
        <p className="text-sm text-muted-foreground">
          {t("team.newTeamLeaveCurrent", { name: snapshot.organization.name })}
        </p>
      ) : null}

      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
        <li>{t("team.newTeamPlanFree")}</li>
        <li>{t("team.newTeamPlanPaid")}</li>
      </ul>

      <CreateWorkspaceCard redirectTo="/account?workspace=created" />
    </div>
  );
}
