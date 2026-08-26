"use client";

import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { switchOrganization } from "@/lib/session";
import { roleLabel } from "@/lib/team";
import type { User } from "@/types/api";

export function PersonalWorkspaceHint({
  user,
  actionLabel = "Ir al equipo",
}: {
  user?: User;
  actionLabel?: string;
}) {
  const companyOrgs = useMemo(
    () => user?.memberships.filter((item) => !item.organization.is_personal) ?? [],
    [user],
  );

  return (
    <Card>
      <CardTitle>Estás en el workspace personal</CardTitle>
      <CardDescription>
        Invitaciones, grupos y la lista de miembros viven en un equipo de empresa. Cambia de workspace o
        crea uno nuevo.
      </CardDescription>
      {companyOrgs.length ? (
        <ul className="mt-4 space-y-2">
          {companyOrgs.map((membership) => (
            <li
              key={membership.organization_id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{membership.organization.name}</p>
                <p className="text-xs text-muted-foreground">{roleLabel[membership.role]}</p>
              </div>
              <Button size="sm" onClick={() => switchOrganization(membership.organization_id)}>
                {actionLabel}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">Aún no tienes un equipo. Créalo más abajo.</p>
      )}
    </Card>
  );
}
