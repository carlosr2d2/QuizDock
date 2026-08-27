"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";

export default function RecoveryPage() {
  const t = useT();
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    const form = new FormData(event.currentTarget);
    try {
      await apiFetch<void>("/api/v1/auth/recovery", {
        method: "POST",
        body: { email: form.get("email") },
      });
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("auth.recoveryError"));
      setPending(false);
    }
  }

  if (sent) {
    return (
      <div className="w-full max-w-sm space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.checkEmail")}</h1>
        <p className="text-sm text-muted-foreground">{t("auth.checkEmailBody")}</p>
        <p className="text-sm text-muted-foreground">
          <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
            {t("auth.backToLogin")}
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="w-full max-w-sm space-y-5" method="post">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("auth.recoveryTitle")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("auth.recoveryBody")}</p>
      </div>
      <div className="space-y-2">
        <Label htmlFor="email">{t("common.email")}</Label>
        <Input id="email" name="email" type="email" required autoComplete="email" />
      </div>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="submit" className="w-full" loading={pending}>
        {pending ? t("auth.sending") : t("auth.sendLink")}
      </Button>
      <p className="text-sm text-muted-foreground">
        {t("auth.rememberIt")}{" "}
        <Link href="/login" className="text-foreground underline-offset-4 hover:underline">
          {t("auth.enter")}
        </Link>
      </p>
    </form>
  );
}
