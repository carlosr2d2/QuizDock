"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageLoader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { authWorkspaceId, inviteTokenFromNext, safeNextPath, setSession } from "@/lib/session";
import type { AuthResponse } from "@/types/api";

export default function LoginPage() {
  return (
    <Suspense fallback={<PageLoader label="Cargando…" />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next");
  const inviteToken = inviteTokenFromNext(nextPath);
  const registerHref = inviteToken ? `/register?invite=${encodeURIComponent(inviteToken)}` : "/register";
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiFetch<AuthResponse>("/api/v1/auth/login", {
        method: "POST",
        body: {
          email: form.get("email"),
          password: form.get("password"),
          invite_token: inviteToken,
        },
      });
      const orgId = authWorkspaceId(result.user, result.organization_id);
      if (!orgId) throw new Error("No hay workspace asociado");
      await setSession(result.access_token, orgId, JSON.stringify(result.user));
      const joinedTeam = result.user.memberships.some(
        (item) => item.organization_id === orgId && !item.organization.is_personal,
      );
      window.location.assign(joinedTeam ? "/overview" : safeNextPath(nextPath));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5" method="post">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Entrar</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {inviteToken
            ? "Entra con el correo de la invitación para unirte al equipo."
            : "Accede a tu workspace personal o de equipo."}
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">Correo</Label>
        <Input id="email" name="email" type="email" required autoComplete="email" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Contraseña</Label>
        <Input id="password" name="password" type="password" required autoComplete="current-password" />
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full" loading={pending}>
        {pending ? "Entrando…" : "Continuar"}
      </Button>
      <p className="text-sm text-muted-foreground">
        ¿No tienes cuenta?{" "}
        <Link href={registerHref} className="text-foreground underline-offset-4 hover:underline">
          Crear una
        </Link>
        {" · "}
        <Link href="/recovery" className="text-foreground underline-offset-4 hover:underline">
          Recuperar acceso
        </Link>
      </p>
    </form>
  );
}
