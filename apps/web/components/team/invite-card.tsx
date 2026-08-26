"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { inviteRoles, roleLabel } from "@/lib/team";
import { formatDate } from "@/lib/utils";
import type { Invitation, MembershipRole, TeamSnapshot } from "@/types/api";

type InviteNotice = { email: string; sent: boolean };

export function InviteCard({ snapshot }: { snapshot: TeamSnapshot }) {
  const queryClient = useQueryClient();
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [notice, setNotice] = useState<InviteNotice | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const pendingInvites = snapshot.invitations.filter((item) => item.status === "pending");

  async function afterDeliver(item: Invitation) {
    setInviteError(null);
    setNotice({ email: item.email, sent: Boolean(item.email_sent) });
    await queryClient.invalidateQueries({ queryKey: ["team"] });
    if (item.token && !item.email_sent) {
      await navigator.clipboard.writeText(`${window.location.origin}/invite/${item.token}`);
      setCopiedId(item.id);
    }
  }

  const invite = useMutation({
    mutationFn: (body: { email: string; role: MembershipRole }) =>
      apiFetch<Invitation>("/api/v1/organizations/current/invitations", { method: "POST", body }),
    onSuccess: (item) => void afterDeliver(item),
    onError: (error: Error) => setInviteError(error.message),
  });

  const resend = useMutation({
    mutationFn: (invitationId: string) =>
      apiFetch<Invitation>(`/api/v1/organizations/current/invitations/${invitationId}/resend`, {
        method: "POST",
      }),
    onSuccess: (item) => void afterDeliver(item),
    onError: (error: Error) => setInviteError(error.message),
  });

  const revoke = useMutation({
    mutationFn: (invitationId: string) =>
      apiFetch<void>(`/api/v1/organizations/current/invitations/${invitationId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team"] }),
  });

  async function copyInvite(item: Invitation) {
    if (!item.token) return;
    const url = `${window.location.origin}/invite/${item.token}`;
    await navigator.clipboard.writeText(url);
    setCopiedId(item.id);
  }

  function onInvite(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setInviteError(null);
    const form = new FormData(event.currentTarget);
    invite.mutate({
      email: String(form.get("email") ?? ""),
      role: (form.get("role") as MembershipRole) || "member",
    });
    event.currentTarget.reset();
  }

  if (!snapshot.can_manage) {
    return (
      <p className="text-sm text-muted-foreground">
        Solo el propietario o un administrador puede enviar invitaciones.
      </p>
    );
  }

  return (
    <Card>
      <CardDescription>
        Enviamos un correo con el enlace. El invitado entra con el mismo correo. Si el envío falla,
        copia el enlace.
      </CardDescription>
      <form onSubmit={onInvite} className="mt-4 grid gap-3 sm:grid-cols-[1fr_8rem_auto] sm:items-end">
        <div className="space-y-2">
          <Label htmlFor="invite-email">Correo</Label>
          <Input id="invite-email" name="email" type="email" required placeholder="ana@empresa.com" />
        </div>
        <div className="space-y-2">
          <Label htmlFor="invite-role">Rol</Label>
          <select
            id="invite-role"
            name="role"
            defaultValue="member"
            className="h-10 w-full rounded-md border border-border bg-card px-3 text-sm"
          >
            {inviteRoles.map((role) => (
              <option key={role} value={role}>
                {roleLabel[role]}
              </option>
            ))}
          </select>
        </div>
        <Button type="submit" loading={invite.isPending}>
          {invite.isPending ? "Enviando…" : "Invitar"}
        </Button>
      </form>
      {inviteError ? <p className="mt-3 text-sm text-destructive">{inviteError}</p> : null}
      {notice ? (
        <p className={`mt-3 text-sm ${notice.sent ? "text-foreground" : "text-destructive"}`}>
          {notice.sent
            ? `Correo enviado a ${notice.email}.`
            : `No se pudo enviar el correo a ${notice.email}. Copia el enlace y envíalo tú.`}
        </p>
      ) : null}

      {pendingInvites.length ? (
        <ul className="mt-5 divide-y divide-border rounded-xl border border-border">
          {pendingInvites.map((item) => (
            <li
              key={item.id}
              className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
            >
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{item.email}</p>
                <p className="text-xs text-muted-foreground">
                  {roleLabel[item.role]} · caduca {formatDate(item.expires_at)}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => resend.mutate(item.id)}
                  loading={resend.isPending && resend.variables === item.id}
                >
                  Reenviar
                </Button>
                <Button size="sm" variant="outline" onClick={() => void copyInvite(item)}>
                  {copiedId === item.id ? "Copiado" : "Copiar enlace"}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => revoke.mutate(item.id)}
                  loading={revoke.isPending && revoke.variables === item.id}
                >
                  Anular
                </Button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-muted-foreground">Todavía no hay invitaciones pendientes.</p>
      )}
    </Card>
  );
}
