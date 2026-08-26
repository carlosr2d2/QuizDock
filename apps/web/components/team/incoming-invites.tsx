"use client";

import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { getToken, setSession } from "@/lib/session";
import { roleLabel } from "@/lib/team";
import { formatDate } from "@/lib/utils";
import type { InvitationAccept, MyInvitation, User } from "@/types/api";

export function IncomingInvites({ items, loading }: { items?: MyInvitation[]; loading: boolean }) {
  const accept = useMutation({
    mutationFn: (token: string) =>
      apiFetch<InvitationAccept>(`/api/v1/invitations/${token}/accept`, { method: "POST" }),
    onSuccess: async (result) => {
      const token = getToken();
      const user = await apiFetch<User>("/api/v1/auth/me");
      if (!token) return;
      await setSession(token, result.organization.id, JSON.stringify(user));
      window.location.assign("/team/members");
    },
  });

  if (loading) return <Loader label="Buscando invitaciones…" />;
  if (!items?.length) return null;

  return (
    <Card>
      <CardTitle>Invitaciones para ti</CardTitle>
      <CardDescription>Acepta para unirte al workspace. Tus documentos personales no se mezclan.</CardDescription>
      <ul className="mt-4 space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{item.organization_name}</p>
              <p className="text-xs text-muted-foreground">
                {roleLabel[item.role]} · caduca {formatDate(item.expires_at)}
              </p>
            </div>
            <Button
              size="sm"
              loading={accept.isPending && accept.variables === item.token}
              onClick={() => accept.mutate(item.token)}
            >
              Aceptar
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
