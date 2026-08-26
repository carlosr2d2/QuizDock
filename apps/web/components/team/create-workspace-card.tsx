"use client";

import { useMutation } from "@tanstack/react-query";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { getToken, setSession } from "@/lib/session";
import type { Organization, User } from "@/types/api";

export function CreateWorkspaceCard({ redirectTo = "/team/members" }: { redirectTo?: string }) {
  const [error, setError] = useState<string | null>(null);
  const createOrg = useMutation({
    mutationFn: (name: string) =>
      apiFetch<Organization>("/api/v1/organizations", { method: "POST", body: { name } }),
    onSuccess: async (org) => {
      const token = getToken();
      const user = await apiFetch<User>("/api/v1/auth/me");
      if (!token) return;
      await setSession(token, org.id, JSON.stringify(user));
      window.location.assign(redirectTo);
    },
    onError: (err: Error) => setError(err.message),
  });

  function onCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const name = String(new FormData(event.currentTarget).get("name") ?? "").trim();
    if (name) createOrg.mutate(name);
  }

  return (
    <Card>
      <CardTitle>Nuevo equipo</CardTitle>
      <CardDescription>
        Crea un workspace compartido. Cada equipo tiene sus propios documentos y créditos.
      </CardDescription>
      <form onSubmit={onCreate} className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="min-w-0 flex-1 space-y-2">
          <Label htmlFor="team-name">Nombre</Label>
          <Input id="team-name" name="name" required minLength={2} placeholder="Academia Norte" />
        </div>
        <Button type="submit" loading={createOrg.isPending}>
          {createOrg.isPending ? "Creando…" : "Crear equipo"}
        </Button>
      </form>
      {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
    </Card>
  );
}
