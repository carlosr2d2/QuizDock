"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { Loader } from "@/components/ui/loader";
import { apiFetch, ApiError } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { getToken, setSession } from "@/lib/session";
import { formatDate } from "@/lib/utils";
import type { InvitationAccept, InvitationPublic, User } from "@/types/api";

function invitationStatus(value: string | undefined): string {
  return value?.split(".").pop()?.toLowerCase() ?? "";
}

export default function InvitePage() {
  const { t, locale } = useI18n();
  const params = useParams<{ token: string }>();
  const token = params.token;
  const [loggedIn, setLoggedIn] = useState(false);
  const [entering, setEntering] = useState(false);
  const [enterError, setEnterError] = useState<string | null>(null);
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

  const enterWorkspace = useCallback(
    async (orgId: string) => {
      const access = getToken();
      if (!access) {
        throw new Error(t("invite.sessionMissing"));
      }
      const user = await apiFetch<User>("/api/v1/auth/me");
      await setSession(access, orgId, JSON.stringify(user));
      window.location.assign("/overview");
    },
    [t],
  );

  const accept = useMutation({
    mutationFn: () => apiFetch<InvitationAccept>(`/api/v1/invitations/${token}/accept`, { method: "POST" }),
    onSuccess: async (result) => {
      try {
        await enterWorkspace(result.organization.id);
      } catch (err) {
        setEnterError(err instanceof Error ? err.message : t("invite.joinError"));
      }
    },
  });

  const invite = preview.data;
  const status = invitationStatus(invite?.status);
  const expiredByDate = Boolean(invite && new Date(invite.expires_at).getTime() <= Date.now());
  const isPending = status === "pending" && !expiredByDate;
  const isExpired = status === "expired" || (status === "pending" && expiredByDate);
  const emailMatches = Boolean(
    me.data && invite && me.data.email.toLowerCase() === invite.email.toLowerCase(),
  );
  const alreadyMember = Boolean(
    me.data &&
      invite &&
      me.data.memberships.some((item) => item.organization_id === invite.organization_id),
  );
  const canEnter = alreadyMember || (emailMatches && (isPending || status === "accepted"));
  const wrongAccount = Boolean(loggedIn && me.data && invite && !emailMatches);

  useEffect(() => {
    if (!invite || !emailMatches || autoStarted.current) return;
    if (alreadyMember || status === "accepted") {
      autoStarted.current = true;
      setEntering(true);
      void enterWorkspace(invite.organization_id)
        .catch((err: unknown) => {
          setEnterError(err instanceof Error ? err.message : t("invite.joinError"));
        })
        .finally(() => setEntering(false));
      return;
    }
    if (isPending) {
      autoStarted.current = true;
      accept.mutate();
    }
  }, [alreadyMember, emailMatches, enterWorkspace, invite, isPending, status, t]);

  const error =
    enterError ??
    (preview.error instanceof ApiError
      ? preview.error.message
      : preview.error
        ? t("invite.loadError")
        : accept.error instanceof Error
          ? accept.error.message
          : null);

  const role = invite ? t(`role.${invite.role}`) : "";
  const busy = accept.isPending || entering;
  const description = !invite
    ? null
    : alreadyMember
      ? t("invite.alreadyMember")
      : isExpired
        ? t("invite.expired")
        : status === "revoked"
          ? t("invite.revoked")
          : t("invite.roleExpires", {
              org: invite.organization_name,
              role,
              date: formatDate(invite.expires_at, locale),
            });

  async function onPrimary() {
    if (!invite) return;
    setEnterError(null);
    if (isPending && !alreadyMember) {
      accept.mutate();
      return;
    }
    setEntering(true);
    try {
      await enterWorkspace(invite.organization_id);
    } catch (err) {
      setEnterError(err instanceof Error ? err.message : t("invite.joinError"));
    } finally {
      setEntering(false);
    }
  }

  return (
    <Card className="w-full max-w-md">
      <CardTitle>{t("invite.title")}</CardTitle>
      {invite ? (
        <CardDescription>{description}</CardDescription>
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
        {invite && loggedIn && me.isLoading ? <Loader label={t("invite.loading")} /> : null}
        {invite && loggedIn && canEnter ? (
          <Button onClick={() => void onPrimary()} loading={busy}>
            {busy
              ? t("invite.acceptingJoin")
              : alreadyMember || status === "accepted"
                ? t("invite.enterTeam")
                : t("invite.acceptEnter")}
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
