"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { apiFetch, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { getToken, setSession } from "@/lib/session";
import { formatDate } from "@/lib/utils";
import type { InvitationAccept, InvitationPublic, User } from "@/types/api";

export default function InvitePage() {
  const { t, locale } = useI18n();
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
        ? t("invite.loadError")
        : accept.error instanceof Error
          ? accept.error.message
          : null;

  const role = invite ? t(`role.${invite.role}`) : "";

  return (
    <Card className="w-full max-w-md">
      <CardTitle>{t("invite.title")}</CardTitle>
      {invite ? (
        <CardDescription>
          {t("invite.roleExpires", {
            org: invite.organization_name,
            role,
            date: formatDate(invite.expires_at, locale),
          })}
        </CardDescription>
      ) : preview.isLoading ? (
        <Loader label={t("invite.loading")} className="mt-2" />
      ) : (
        <CardDescription>{t("invite.invalid")}</CardDescription>
      )}

      {wrongAccount ? (
        <p className="mt-4 text-sm text-destructive">
          {t("invite.forEmail", { email: invite?.email ?? "", current: me.data?.email ?? "" })}
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
            {accept.isPending || accept.isSuccess ? t("invite.acceptingJoin") : t("invite.acceptEnter")}
          </Button>
        ) : null}
        {invite && !loggedIn ? (
          <>
            <Link href={`/register?invite=${token}`}>
              <Button>{t("invite.createJoin")}</Button>
            </Link>
            <Link href={`/login?next=/invite/${token}`}>
              <Button variant="outline">{t("invite.haveAccount")}</Button>
            </Link>
          </>
        ) : null}
        {wrongAccount ? (
          <Link href={`/login?next=/invite/${token}`}>
            <Button>{t("invite.enterAs", { email: invite?.email ?? "" })}</Button>
          </Link>
        ) : null}
        <Link href="/" className="text-sm text-muted-foreground hover:underline">
          {t("invite.goHome")}
        </Link>
      </div>
    </Card>
  );
}
