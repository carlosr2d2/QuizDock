"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader, PageLoader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { LOCALE_STORAGE_KEY, parseLocale } from "@/lib/i18n/config";
import { syncLocaleFromUser, useT } from "@/lib/i18n/provider";
import { authWorkspaceId, setSession } from "@/lib/session";
import type { AuthResponse, InvitationPublic } from "@/types/api";

export default function RegisterPage() {
  const t = useT();
  return (
    <Suspense fallback={<PageLoader label={t("common.loading")} />}>
      <RegisterForm />
    </Suspense>
  );
}

function RegisterForm() {
  const t = useT();
  const searchParams = useSearchParams();
  const inviteToken = searchParams.get("invite");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const invite = useQuery({
    queryKey: ["invitation", inviteToken],
    queryFn: () => apiFetch<InvitationPublic>(`/api/v1/invitations/${inviteToken}`),
    enabled: Boolean(inviteToken),
    retry: false,
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(event.currentTarget);
    try {
      const result = await apiFetch<AuthResponse>("/api/v1/auth/register", {
        method: "POST",
        body: {
          full_name: form.get("full_name"),
          email: form.get("email"),
          password: form.get("password"),
          invite_token: inviteToken,
          locale: parseLocale(localStorage.getItem(LOCALE_STORAGE_KEY)),
        },
      });
      const orgId = authWorkspaceId(result.user, result.organization_id);
      if (!orgId) throw new Error(t("auth.noWorkspace"));
      syncLocaleFromUser(result.user);
      await setSession(result.access_token, orgId, JSON.stringify(result.user));
      window.location.assign("/overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.registerError"));
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.registerTitle")}</h1>
        {inviteToken && invite.isLoading ? (
          <Loader label={t("auth.loadingInvite")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {invite.data
              ? t("auth.registerInvite", { org: invite.data.organization_name })
              : t("auth.registerBody")}
          </p>
        )}
      </div>
      <div className="space-y-2">
        <Label htmlFor="full_name">{t("common.name")}</Label>
        <Input id="full_name" name="full_name" required autoComplete="name" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">{t("common.email")}</Label>
        <Input
          id="email"
          name="email"
          type="email"
          required
          autoComplete="email"
          key={invite.data?.email ?? "email"}
          defaultValue={invite.data?.email ?? ""}
          readOnly={Boolean(invite.data?.email)}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">{t("common.password")}</Label>
        <Input
          id="password"
          name="password"
          type="password"
          minLength={8}
          required
          autoComplete="new-password"
        />
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full" loading={pending}>
        {pending ? t("auth.creating") : inviteToken ? t("auth.registerJoin") : t("auth.registerSubmit")}
      </Button>
      <p className="text-sm text-muted-foreground">
        {t("auth.haveAccount")}{" "}
        <Link
          href={inviteToken ? `/login?next=/invite/${inviteToken}` : "/login"}
          className="text-foreground underline-offset-4 hover:underline"
        >
          {t("auth.enter")}
        </Link>
      </p>
    </form>
  );
}
