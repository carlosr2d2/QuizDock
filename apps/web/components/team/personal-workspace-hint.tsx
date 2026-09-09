"use client";

import Link from "next/link";
import { useMemo } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { useT } from "@/lib/i18n/provider";
import { switchOrganization } from "@/lib/session";
import type { User } from "@/types/api";

export function PersonalWorkspaceHint({
  user,
  actionLabel,
}: {
  user?: User;
  actionLabel?: string;
}) {
  const t = useT();
  const companyOrgs = useMemo(
    () => user?.memberships.filter((item) => !item.organization.is_personal) ?? [],
    [user],
  );
  const label = actionLabel ?? t("team.goTeam");

  return (
    <Card>
      <CardTitle>{t("team.personalTitle")}</CardTitle>
      <CardDescription>{t("team.personalBody")}</CardDescription>
      {companyOrgs.length ? (
        <ul className="mt-4 space-y-2">
          {companyOrgs.map((membership) => (
            <li
              key={membership.organization_id}
              className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{membership.organization.name}</p>
                <p className="text-xs text-muted-foreground">{t(`role.${membership.role}`)}</p>
              </div>
              <Button size="sm" onClick={() => switchOrganization(membership.organization_id)}>
                {label}
              </Button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">
          {t("team.noTeamYet")}{" "}
          <Link href="/team/new" className="font-medium text-accent hover:underline">
            {t("nav.createTeam")}
          </Link>
        </p>
      )}
    </Card>
  );
}
