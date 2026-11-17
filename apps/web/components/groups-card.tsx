"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  listItemClass,
  listRowHoverClass,
  listRowSelectedClass,
  surfaceListClass,
} from "@/components/ui/card";
import { checkboxClass, Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { TeamGroup, TeamMember } from "@/types/api";

export function GroupsCard({
  groups,
  members,
  canManage,
}: {
  groups: TeamGroup[];
  members: TeamMember[];
  canManage: boolean;
}) {
  const t = useT();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(groups[0]?.id ?? null);

  const create = useMutation({
    mutationFn: (name: string) =>
      apiFetch<TeamGroup>("/api/v1/organizations/current/groups", { method: "POST", body: { name } }),
    onSuccess: async (group) => {
      setError(null);
      setOpenId(group.id);
      await queryClient.invalidateQueries({ queryKey: ["team"] });
    },
    onError: (err: Error) => setError(err.message),
  });
  const remove = useMutation({
    mutationFn: (groupId: string) =>
      apiFetch<void>(`/api/v1/organizations/current/groups/${groupId}`, { method: "DELETE" }),
    onSuccess: async (_, groupId) => {
      if (openId === groupId) setOpenId(null);
      await queryClient.invalidateQueries({ queryKey: ["team"] });
    },
    onError: (err: Error) => setError(err.message),
  });
  const saveMembers = useMutation({
    mutationFn: ({ groupId, userIds }: { groupId: string; userIds: string[] }) =>
      apiFetch<TeamGroup>(`/api/v1/organizations/current/groups/${groupId}/members`, {
        method: "PUT",
        body: { user_ids: userIds },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team"] }),
    onError: (err: Error) => setError(err.message),
  });

  function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = String(new FormData(event.currentTarget).get("name") ?? "").trim();
    if (!name) return;
    create.mutate(name);
    event.currentTarget.reset();
  }

  return (
    <div className="space-y-5">
      {canManage ? (
        <Card>
          <form onSubmit={onCreate} className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="min-w-0 flex-1 space-y-2">
              <Label htmlFor="group-name">{t("common.name")}</Label>
              <Input id="group-name" name="name" required minLength={2} placeholder={t("team.groupPlaceholder")} />
            </div>
            <Button type="submit" loading={create.isPending}>
              {create.isPending ? t("team.creating") : t("team.createGroup")}
            </Button>
          </form>
        </Card>
      ) : null}
      {error ? <p className="text-sm text-destructive">{error}</p> : null}

      {groups.length ? (
        <ul className={surfaceListClass}>
          {groups.map((group) => {
            const isSelected = openId === group.id;
            const panelId = `group-panel-${group.id}`;
            return (
              <li
                key={group.id}
                className={cn(
                  "relative transition-colors duration-200",
                  isSelected ? listRowSelectedClass : "hover:bg-muted/40",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "absolute inset-y-0 left-0 w-0.5 bg-accent transition-opacity duration-200",
                    isSelected ? "opacity-100" : "opacity-0",
                  )}
                />
                <div className={cn("flex items-center justify-between gap-4", listItemClass)}>
                  <button
                    type="button"
                    aria-expanded={isSelected}
                    aria-controls={panelId}
                    className={cn("min-w-0 flex-1 rounded-md px-1 py-0.5 text-left", listRowHoverClass)}
                    onClick={() => setOpenId(isSelected ? null : group.id)}
                  >
                    <p className={cn("truncate text-sm font-medium", isSelected && "text-accent")}>{group.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {group.member_count} {group.member_count === 1 ? t("exams.memberOne") : t("exams.memberOther")}
                    </p>
                  </button>
                  {canManage ? (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => remove.mutate(group.id)}
                      loading={remove.isPending && remove.variables === group.id}
                    >
                      {t("team.delete")}
                    </Button>
                  ) : null}
                </div>
                <div
                  id={panelId}
                  className={cn(
                    "grid transition-[grid-template-rows,opacity] duration-300 ease-out",
                    isSelected ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0",
                  )}
                >
                  <div className="min-h-0 overflow-hidden">
                    <GroupMembersEditor
                      group={group}
                      members={members}
                      canManage={canManage}
                      saving={saveMembers.isPending && saveMembers.variables?.groupId === group.id}
                      onSave={(userIds) => saveMembers.mutate({ groupId: group.id, userIds })}
                    />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">
          {canManage ? t("team.groupHint") : t("team.noGroups")}
        </p>
      )}
    </div>
  );
}

function GroupMembersEditor({
  group,
  members,
  canManage,
  saving,
  onSave,
}: {
  group: TeamGroup;
  members: TeamMember[];
  canManage: boolean;
  saving: boolean;
  onSave: (userIds: string[]) => void;
}) {
  const t = useT();
  const [selected, setSelected] = useState<string[]>(() => group.members.map((item) => item.user_id));
  const selectedSet = new Set(selected);

  function toggle(userId: string) {
    setSelected((current) =>
      current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId],
    );
  }

  if (!canManage) {
    return (
      <ul className="space-y-1 border-t border-border px-5 py-3">
        {group.members.length ? (
          group.members.map((member) => (
            <li key={member.user_id} className="text-sm">
              {member.full_name}{" "}
              <span className="text-muted-foreground">· {member.email}</span>
            </li>
          ))
        ) : (
          <li className="text-sm text-muted-foreground">{t("exams.emptyGroup")}.</li>
        )}
      </ul>
    );
  }

  return (
    <div className="space-y-3 border-t border-border px-5 py-4">
      <ul className="space-y-1">
        {members.map((member) => (
          <li key={member.user_id}>
            <label
              className={cn(
                "flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm",
                listRowHoverClass,
                selectedSet.has(member.user_id) && "bg-muted/50",
              )}
            >
              <input
                type="checkbox"
                className={checkboxClass}
                checked={selectedSet.has(member.user_id)}
                onChange={() => toggle(member.user_id)}
              />
              <span>
                {member.full_name}{" "}
                <span className="text-muted-foreground">· {member.email}</span>
              </span>
            </label>
          </li>
        ))}
      </ul>
      <Button size="sm" type="button" loading={saving} onClick={() => onSave(selected)}>
        {saving ? t("auth.saving") : t("team.saveMembers")}
      </Button>
    </div>
  );
}
