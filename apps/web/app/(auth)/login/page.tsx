"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageLoader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { syncLocaleFromUser, useT } from "@/lib/i18n/provider";
import { authWorkspaceId, inviteTokenFromNext, safeNextPath, setSession } from "@/lib/session";
import type { AuthResponse } from "@/types/api";

export default function LoginPage() {
  const t = useT();
  return (
    <Suspense fallback={<PageLoader label={t("common.loading")} />}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const t = useT();
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
      if (!orgId) throw new Error(t("auth.noWorkspaceLogin"));
      syncLocaleFromUser(result.user);
      await setSession(result.access_token, orgId, JSON.stringify(result.user));
      const joinedTeam = result.user.memberships.some(
        (item) => item.organization_id === orgId && !item.organization.is_personal,
      );
      window.location.assign(joinedTeam ? "/overview" : safeNextPath(nextPath));
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.loginError"));
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5" method="post">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.loginTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {inviteToken ? t("auth.loginInvite") : t("auth.loginBody")}
        </p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">{t("common.email")}</Label>
        <Input id="email" name="email" type="email" required autoComplete="email" />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">{t("common.password")}</Label>
        <Input id="password" name="password" type="password" required autoComplete="current-password" />
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full" loading={pending}>
        {pending ? t("auth.loggingIn") : t("auth.loginSubmit")}
      </Button>
      <p className="text-sm text-muted-foreground">
        {t("auth.noAccount")}{" "}
        <Link href={registerHref} className="text-foreground underline-offset-4 hover:underline">
          {t("auth.createOne")}
        </Link>
        {" · "}
        <Link href="/recovery" className="text-foreground underline-offset-4 hover:underline">
          {t("auth.recoverAccess")}
        </Link>
      </p>
    </form>
  );
}
