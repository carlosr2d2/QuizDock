"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
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

  const selected = groups.find((group) => group.id === openId) ?? null;

  return (
    <Card>
      {canManage ? (
        <form onSubmit={onCreate} className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1 space-y-2">
            <Label htmlFor="group-name">{t("common.name")}</Label>
            <Input id="group-name" name="name" required minLength={2} placeholder={t("team.groupPlaceholder")} />
          </div>
          <Button type="submit" loading={create.isPending}>
            {create.isPending ? t("team.creating") : t("team.createGroup")}
          </Button>
        </form>
      ) : null}
      {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}

      {groups.length ? (
        <ul className="mt-5 divide-y divide-border rounded-xl border border-border">
          {groups.map((group) => (
            <li key={group.id}>
              <div className="flex items-center justify-between gap-3 px-4 py-3">
                <button
                  type="button"
                  className="min-w-0 flex-1 rounded-md px-1 py-0.5 text-left hover:bg-muted/70"
                  onClick={() => setOpenId(openId === group.id ? null : group.id)}
                >
                  <p className="truncate text-sm font-medium">{group.name}</p>
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
              {selected?.id === group.id ? (
                <GroupMembersEditor
                  key={group.id}
                  group={group}
                  members={members}
                  canManage={canManage}
                  saving={saveMembers.isPending}
                  onSave={(userIds) => saveMembers.mutate({ groupId: group.id, userIds })}
                />
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">
          {canManage ? t("team.groupHint") : t("team.noGroups")}
        </p>
      )}
    </Card>
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
      <ul className="space-y-1 border-t border-border px-4 py-3">
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
    <div className="space-y-3 border-t border-border px-4 py-3">
      <ul className="space-y-2">
        {members.map((member) => (
          <li key={member.user_id}>
            <label className="flex cursor-pointer items-center gap-3 text-sm">
              <input
                type="checkbox"
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
