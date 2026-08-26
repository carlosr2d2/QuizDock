"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { MemberProgressPanel } from "@/components/member-progress-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { surfaceListClass } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { roleLabel } from "@/lib/team";
import type { TeamMember, TeamSnapshot } from "@/types/api";

export function MembersList({
  snapshot,
  currentUserId,
}: {
  snapshot: TeamSnapshot;
  currentUserId?: string;
}) {
  const queryClient = useQueryClient();
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null);

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      apiFetch<void>(`/api/v1/organizations/current/members/${userId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team"] }),
  });

  if (!snapshot.members.length) {
    return (
      <EmptyState title="Sin miembros" description="Invita a alguien desde la sección Invitar." />
    );
  }

  return (
    <>
      <ul className={surfaceListClass}>
        {snapshot.members.map((member) => {
          const isSelf = member.user_id === currentUserId;
          const canRemove = snapshot.can_manage && !isSelf && member.role !== "owner";
          const canOpenProgress =
            isSelf || snapshot.role === "owner" || snapshot.role === "admin" || snapshot.role === "auditor";
          return (
            <li key={member.id} className="flex items-center justify-between gap-4 px-5 py-4">
              <button
                type="button"
                className="min-w-0 flex-1 rounded-md px-1 py-0.5 text-left transition-colors hover:bg-muted/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-default disabled:hover:bg-transparent"
                onClick={() => canOpenProgress && setSelectedMember(member)}
                disabled={!canOpenProgress}
              >
                <p className="truncate text-sm font-medium">
                  {member.full_name}
                  {isSelf ? " · tú" : ""}
                </p>
                <p className="text-xs text-muted-foreground">
                  {member.email}
                  {canOpenProgress ? " · ver exámenes" : ""}
                </p>
              </button>
              <div className="flex shrink-0 items-center gap-2">
                <Badge>{roleLabel[member.role]}</Badge>
                {canRemove ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => removeMember.mutate(member.user_id)}
                    loading={removeMember.isPending && removeMember.variables === member.user_id}
                  >
                    Quitar
                  </Button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
      {selectedMember ? (
        <MemberProgressPanel member={selectedMember} onClose={() => setSelectedMember(null)} />
      ) : null}
    </>
  );
}
