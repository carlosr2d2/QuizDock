"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { apiFetch, ApiError } from "@/lib/api";
import { getToken, setSession } from "@/lib/session";
import { formatDate } from "@/lib/utils";
import type { InvitationAccept, InvitationPublic, User } from "@/types/api";

const roleLabel: Record<string, string> = {
  owner: "propietario",
  admin: "admin",
  member: "miembro",
  auditor: "auditor",
};

export default function InvitePage() {
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [loggedIn, setLoggedIn] = useState(false);
  const autoStarted = useRef(false);

  useEffect(() => {
    setLoggedIn(Boolean(getToken()));
  }, []);

  const preview = useQuery({
    queryKey: ["invitation", token],
    queryFn: () => apiFetch<InvitationPublic>(`/api/v1/invitations/${token}`),
    enabled: Boolean(token),
    retry: false,
  });

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
    enabled: loggedIn,
    retry: false,
  });

  const accept = useMutation({
    mutationFn: () => apiFetch<InvitationAccept>(`/api/v1/invitations/${token}/accept`, { method: "POST" }),
    onSuccess: async (result) => {
      const access = getToken();
      const user = await apiFetch<User>("/api/v1/auth/me");
      if (!access) return;
      await setSession(access, result.organization.id, JSON.stringify(user));
      window.location.assign("/overview");
    },
  });

  const invite = preview.data;
  const emailMatches =
    Boolean(me.data && invite && me.data.email.toLowerCase() === invite.email.toLowerCase());
  const wrongAccount = Boolean(loggedIn && me.data && invite && !emailMatches);

  useEffect(() => {
    if (!emailMatches || invite?.status !== "pending" || autoStarted.current) return;
    autoStarted.current = true;
    accept.mutate();
  }, [emailMatches, invite?.status, accept]);

  const error =
    preview.error instanceof ApiError
      ? preview.error.message
      : preview.error
        ? "No se pudo cargar la invitación."
        : accept.error instanceof Error
          ? accept.error.message
          : null;

  return (
    <Card className="w-full max-w-md">
      <CardTitle>Invitación a un equipo</CardTitle>
      {invite ? (
        <CardDescription>
          {invite.organization_name} · rol {roleLabel[invite.role] ?? invite.role}. Caduca{" "}
          {formatDate(invite.expires_at)}.
        </CardDescription>
      ) : preview.isLoading ? (
        <Loader label="Cargando invitación…" className="mt-2" />
      ) : (
        <CardDescription>Esta invitación no es válida o ya caducó.</CardDescription>
      )}

      {wrongAccount ? (
        <p className="mt-4 text-sm text-destructive">
          Esta invitación es para {invite?.email}. Ahora mismo hay otra sesión ({me.data?.email}). Cierra
          sesión y entra con el correo invitado.
        </p>
      ) : null}

      {error && !wrongAccount ? <p className="mt-4 text-sm text-destructive">{error}</p> : null}

      <div className="mt-6 flex flex-wrap gap-2">
        {invite && loggedIn && emailMatches ? (
          <Button
            onClick={() => accept.mutate()}
            loading={accept.isPending || accept.isSuccess}
            disabled={invite.status !== "pending"}
          >
            {accept.isPending || accept.isSuccess ? "Uniendo…" : "Aceptar e entrar"}
          </Button>
        ) : null}
        {invite && !loggedIn ? (
          <>
            <Link href={`/register?invite=${token}`}>
              <Button>Crear cuenta y unirme</Button>
            </Link>
            <Link href={`/login?next=/invite/${token}`}>
              <Button variant="outline">Ya tengo cuenta</Button>
            </Link>
          </>
        ) : null}
        {wrongAccount ? (
          <Link href={`/login?next=/invite/${token}`}>
            <Button>Entrar con {invite?.email}</Button>
          </Link>
        ) : null}
        <Link href="/" className="text-sm text-muted-foreground hover:underline">
          Ir al inicio
        </Link>
      </div>
    </Card>
  );
}
