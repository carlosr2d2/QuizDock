"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader } from "@/components/ui/loader";
import { apiFetch, ApiError } from "@/lib/api";
import { syncLocaleFromUser, useT } from "@/lib/i18n/provider";
import { authWorkspaceId, setSession } from "@/lib/session";
import type { AuthResponse } from "@/types/api";

export default function ResetPasswordPage() {
  const t = useT();
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const preview = useQuery({
    queryKey: ["recovery", token],
    queryFn: () => apiFetch<{ valid: boolean }>(`/api/v1/auth/recovery/${token}`),
    enabled: Boolean(token),
    retry: false,
  });

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const confirm = String(form.get("confirm") ?? "");
    if (password !== confirm) {
      setError(t("auth.mismatch"));
      return;
    }
    setPending(true);
    try {
      const result = await apiFetch<AuthResponse>(`/api/v1/auth/recovery/${token}`, {
        method: "POST",
        body: { password },
      });
      const orgId = authWorkspaceId(result.user, result.organization_id);
      if (!orgId) throw new Error(t("auth.noWorkspaceLogin"));
      syncLocaleFromUser(result.user);
      await setSession(result.access_token, orgId, JSON.stringify(result.user));
      window.location.assign("/overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.resetError"));
      setPending(false);
    }
  }

  if (preview.isLoading) {
    return <Loader label={t("auth.checkingLink")} />;
  }

  if (preview.isError) {
    const message =
      preview.error instanceof ApiError ? preview.error.message : t("auth.invalidLinkBody");
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.invalidLink")}</h1>
        <p className="text-sm text-muted-foreground">{message}</p>
        <p className="text-sm text-muted-foreground">
          <Link href="/recovery" className="text-foreground underline-offset-4 hover:underline">
            {t("auth.requestNew")}
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5" method="post">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.resetTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("auth.resetBody")}</p>
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
      <div className="space-y-2">
        <Label htmlFor="confirm">{t("common.confirmPassword")}</Label>
        <Input
          id="confirm"
          name="confirm"
          type="password"
          minLength={8}
          required
          autoComplete="new-password"
        />
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full" loading={pending}>
        {pending ? t("auth.saving") : t("auth.saveAndEnter")}
      </Button>
    </form>
  );
}
