"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";
import { getOrgId } from "@/lib/session";
import type { TeamSnapshot, User } from "@/types/api";

export function useTeamPage() {
  const orgId = typeof window === "undefined" ? null : getOrgId();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
    refetchOnMount: "always",
  });
  const team = useQuery({
    queryKey: ["team", orgId],
    queryFn: () => apiFetch<TeamSnapshot>("/api/v1/organizations/current/team"),
    refetchOnMount: "always",
  });
  const snapshot = team.data;
  const isPersonal = snapshot?.organization.is_personal ?? false;
  return { orgId, me, team, snapshot, isPersonal };
}
