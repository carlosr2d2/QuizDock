"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FormEvent, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle, surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader, PageLoader } from "@/components/ui/loader";
import { MemberProgressPanel } from "@/components/member-progress-panel";
import { apiFetch } from "@/lib/api";
import { getOrgId, getToken, setSession, switchOrganization } from "@/lib/session";
import { formatDate } from "@/lib/utils";
import type {
  Invitation,
  InvitationAccept,
  MembershipRole,
  MyInvitation,
  Organization,
  TeamSnapshot,
  User,
} from "@/types/api";

const roleLabel: Record<MembershipRole, string> = {
  owner: "propietario",
  admin: "admin",
  member: "miembro",
  auditor: "auditor",
};

const inviteRoles: MembershipRole[] = ["member", "admin", "auditor"];

export default function TeamPage() {
  const queryClient = useQueryClient();
  const [createError, setCreateError] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [selectedMember, setSelectedMember] = useState<TeamSnapshot["members"][number] | null>(null);
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
  const mine = useQuery({
    queryKey: ["my-invitations"],
    queryFn: () => apiFetch<MyInvitation[]>("/api/v1/invitations"),
  });

  const createOrg = useMutation({
    mutationFn: (name: string) =>
      apiFetch<Organization>("/api/v1/organizations", { method: "POST", body: { name } }),
    onSuccess: async (org) => {
      const token = getToken();
      const user = await apiFetch<User>("/api/v1/auth/me");
      if (!token) return;
      await setSession(token, org.id, JSON.stringify(user));
      window.location.assign("/team");
    },
    onError: (error: Error) => setCreateError(error.message),
  });

  const invite = useMutation({
    mutationFn: (body: { email: string; role: MembershipRole }) =>
      apiFetch<Invitation>("/api/v1/organizations/current/invitations", { method: "POST", body }),
    onSuccess: async (item) => {
      setInviteError(null);
      await queryClient.invalidateQueries({ queryKey: ["team"] });
      if (item.token) {
        await navigator.clipboard.writeText(`${window.location.origin}/invite/${item.token}`);
        setCopiedId(item.id);
      }
    },
    onError: (error: Error) => setInviteError(error.message),
  });

  const revoke = useMutation({
    mutationFn: (invitationId: string) =>
      apiFetch<void>(`/api/v1/organizations/current/invitations/${invitationId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team"] }),
  });

  const removeMember = useMutation({
    mutationFn: (userId: string) =>
      apiFetch<void>(`/api/v1/organizations/current/members/${userId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team"] }),
  });

  const accept = useMutation({
    mutationFn: (token: string) =>
      apiFetch<InvitationAccept>(`/api/v1/invitations/${token}/accept`, { method: "POST" }),
    onSuccess: async (result) => {
      const token = getToken();
      const user = await apiFetch<User>("/api/v1/auth/me");
      if (!token) return;
      await setSession(token, result.organization.id, JSON.stringify(user));
      window.location.assign("/team");
    },
  });

  const snapshot = team.data;
  const pendingInvites = snapshot?.invitations.filter((item) => item.status === "pending") ?? [];
  const currentUserId = me.data?.id;
  const isPersonal = snapshot?.organization.is_personal ?? false;
  const companyOrgs = useMemo(
    () => me.data?.memberships.filter((item) => !item.organization.is_personal) ?? [],
    [me.data],
  );

  async function copyInvite(item: Invitation) {
    if (!item.token) return;
    const url = `${window.location.origin}/invite/${item.token}`;
    await navigator.clipboard.writeText(url);
    setCopiedId(item.id);
  }

  function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCreateError(null);
    const name = String(new FormData(event.currentTarget).get("name") ?? "").trim();
    if (name) createOrg.mutate(name);
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

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Equipo</h1>
        {team.isLoading ? (
          <Loader label="Cargando workspace…" className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? "Estás en tu workspace personal. Las invitaciones solo existen en un equipo de empresa."
              : `Miembros, roles e invitaciones de ${snapshot?.organization.name ?? "este workspace"}.`}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label="Cargando equipo…" /> : null}

      {team.isError ? (
        <ErrorState
          title="No se pudo cargar el equipo"
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {mine.isLoading ? <Loader label="Buscando invitaciones…" /> : null}
      {mine.data?.length ? (
        <Card>
          <CardTitle>Invitaciones para ti</CardTitle>
          <CardDescription>Acepta para unirte al workspace. Tus documentos personales no se mezclan.</CardDescription>
          <ul className="mt-4 space-y-2">
            {mine.data.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.organization_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {roleLabel[item.role]} · caduca {formatDate(item.expires_at)}
                  </p>
                </div>
                <Button size="sm" loading={accept.isPending && accept.variables === item.token} onClick={() => accept.mutate(item.token)}>
                  Aceptar
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {isPersonal ? (
        <Card>
          <CardTitle>¿Dónde invito?</CardTitle>
          <CardDescription>
            El workspace personal es solo tuyo. Cambia a un equipo de empresa o crea uno nuevo; ahí aparece el
            formulario Invitar.
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
                    Ir e invitar
                  </Button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-4 text-sm text-muted-foreground">
              Aún no tienes un equipo. Crea uno abajo; al crearlo se abre automáticamente.
            </p>
          )}
        </Card>
      ) : null}

      {snapshot?.can_manage ? (
        <Card>
          <CardTitle>Invitar</CardTitle>
          <CardDescription>
            Genera un enlace y envíalo. El invitado entra con el mismo correo. Aún no hay envío automático.
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

          {pendingInvites.length ? (
            <ul className="mt-5 divide-y divide-border rounded-xl border border-border">
              {pendingInvites.map((item) => (
                <li key={item.id} className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.email}</p>
                    <p className="text-xs text-muted-foreground">
                      {roleLabel[item.role]} · caduca {formatDate(item.expires_at)}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
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
      ) : null}

      {!isPersonal && snapshot?.members.length ? (
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
      ) : null}

      {!isPersonal && snapshot && !snapshot.members.length ? (
        <EmptyState title="Sin miembros" description="Invita a alguien con el formulario de arriba." />
      ) : null}

      <Card>
        <CardTitle>Nuevo equipo</CardTitle>
        <CardDescription>Crea un workspace compartido. Cada equipo tiene sus propios documentos y créditos.</CardDescription>
        <form onSubmit={onCreate} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-0 flex-1 space-y-2">
            <Label htmlFor="team-name">Nombre</Label>
            <Input id="team-name" name="name" required minLength={2} placeholder="Academia Norte" />
          </div>
          <Button type="submit" loading={createOrg.isPending}>
            {createOrg.isPending ? "Creando…" : "Crear equipo"}
          </Button>
        </form>
        {createError ? <p className="mt-3 text-sm text-destructive">{createError}</p> : null}
      </Card>

      {selectedMember ? (
        <MemberProgressPanel member={selectedMember} onClose={() => setSelectedMember(null)} />
      ) : null}
    </div>
  );
}
