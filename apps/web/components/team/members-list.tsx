"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { MemberProgressPanel } from "@/components/member-progress-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { listItemClass, listRowHoverClass, surfaceListClass } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { cn, formatDate, formatRelativeTime } from "@/lib/utils";
import type { Invitation, TeamMember, TeamSnapshot } from "@/types/api";

export function MembersList({
  snapshot,
  currentUserId,
}: {
  snapshot: TeamSnapshot;
  currentUserId?: string;
}) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [selectedMember, setSelectedMember] = useState<TeamMember | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [inviteNotice, setInviteNotice] = useState<{ email: string; sent: boolean } | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const pendingInvites = snapshot.invitations.filter((item) => item.status === "pending");

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      apiFetch<void>(`/api/v1/organizations/current/members/${userId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team"] }),
  });

  const resend = useMutation({
    mutationFn: (invitationId: string) =>
      apiFetch<Invitation>(`/api/v1/organizations/current/invitations/${invitationId}/resend`, {
        method: "POST",
      }),
    onSuccess: async (item) => {
      setInviteError(null);
      setInviteNotice({ email: item.email, sent: Boolean(item.email_sent) });
      await queryClient.invalidateQueries({ queryKey: ["team"] });
      if (item.token && !item.email_sent) {
        await navigator.clipboard.writeText(`${window.location.origin}/invite/${item.token}`);
        setCopiedId(item.id);
      }
    },
    onError: (error: Error) => setInviteError(error.message),
  });

  async function copyInvite(item: Invitation) {
    if (!item.token) return;
    await navigator.clipboard.writeText(`${window.location.origin}/invite/${item.token}`);
    setCopiedId(item.id);
  }

  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">{t("team.activeMembers")}</h2>
        {!snapshot.members.length ? (
          <EmptyState title={t("team.emptyMembers")} description={t("team.emptyMembersBody")} />
        ) : (
          <ul className={surfaceListClass}>
            {snapshot.members.map((member) => {
              const isSelf = member.user_id === currentUserId;
              const canRemove = snapshot.can_manage && !isSelf && member.role !== "owner";
              const canOpenProgress =
                isSelf || snapshot.role === "owner" || snapshot.role === "admin" || snapshot.role === "auditor";
              return (
                <li key={member.id} className={`flex items-center justify-between gap-4 ${listItemClass}`}>
                  <button
                    type="button"
                    className={cn(
                      "min-w-0 flex-1 rounded-md px-1 py-0.5 text-left disabled:cursor-default disabled:hover:bg-transparent",
                      listRowHoverClass,
                    )}
                    onClick={() => canOpenProgress && setSelectedMember(member)}
                    disabled={!canOpenProgress}
                  >
                    <p className="truncate text-sm font-medium">
                      {member.full_name}
                      {isSelf ? ` · ${t("team.you")}` : ""}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {member.email}
                      {canOpenProgress ? ` · ${t("team.viewExams")}` : ""}
                    </p>
                    <LastSeenLine member={member} />
                  </button>
                  <div className="flex shrink-0 items-center gap-2">
                    <Badge>{t(`role.${member.role}`)}</Badge>
                    {canRemove ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => removeMember.mutate(member.user_id)}
                        loading={removeMember.isPending && removeMember.variables === member.user_id}
                      >
                        {t("team.remove")}
                      </Button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section className="space-y-3">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{t("team.pendingInvitesTitle")}</h2>
          <p className="text-xs text-muted-foreground">{t("team.pendingInvitesBody")}</p>
        </div>
        {inviteError ? <p className="text-sm text-destructive">{inviteError}</p> : null}
        {inviteNotice ? (
          <p className={`text-sm ${inviteNotice.sent ? "text-foreground" : "text-destructive"}`}>
            {inviteNotice.sent
              ? t("team.sentTo", { email: inviteNotice.email })
              : t("team.sendFailed", { email: inviteNotice.email })}
          </p>
        ) : null}
        {pendingInvites.length ? (
          <ul className={surfaceListClass}>
            {pendingInvites.map((item) => (
              <li
                key={item.id}
                className={`flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between ${listItemClass}`}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.email}</p>
                  <p className="text-xs text-muted-foreground" suppressHydrationWarning>
                    {t("team.invitedOn", { date: formatDate(item.created_at, locale) })}
                    {" · "}
                    {t("team.expiresRole", {
                      role: t(`role.${item.role}`),
                      date: formatDate(item.expires_at, locale),
                    })}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <Badge>{t("team.pendingInvite")}</Badge>
                  {snapshot.can_manage ? (
                    <>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => resend.mutate(item.id)}
                        loading={resend.isPending && resend.variables === item.id}
                      >
                        {t("team.resend")}
                      </Button>
                      {item.token ? (
                        <Button size="sm" variant="outline" onClick={() => void copyInvite(item)}>
                          {copiedId === item.id ? t("team.copied") : t("team.copyLink")}
                        </Button>
                      ) : null}
                    </>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t("team.noPending")}</p>
        )}
      </section>

      {selectedMember ? (
        <MemberProgressPanel member={selectedMember} onClose={() => setSelectedMember(null)} />
      ) : null}
    </div>
  );
}

function LastSeenLine({ member }: { member: TeamMember }) {
  const { t, locale } = useI18n();
  const [label, setLabel] = useState("");

  useEffect(() => {
    if (!member.last_seen_at) {
      setLabel(t("team.neverSeen"));
      return;
    }
    const relative = formatRelativeTime(member.last_seen_at, locale);
    setLabel(t("team.lastSeen", { time: relative ?? t("team.lastSeenNow") }));
  }, [locale, member.last_seen_at, t]);

  return (
    <p className="mt-0.5 text-xs text-muted-foreground" suppressHydrationWarning>
      {label}
    </p>
  );
}
