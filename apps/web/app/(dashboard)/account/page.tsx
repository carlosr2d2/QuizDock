"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader, PageLoader, Skeleton } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { canCreateContent } from "@/lib/permissions";
import { formatDateTime, formatMoney } from "@/lib/utils";
import type {
  BillingCatalog,
  CreditBalance,
  CreditTransaction,
  PaymentOrder,
  User,
} from "@/types/api";

const COUNTRIES = ["CO", "US", "MX", "AR", "CL", "PE", "ES"] as const;

function providerLabel(
  id: string,
  t: (key: string) => string,
  catalog?: BillingCatalog | null,
) {
  const key = `account.provider${id.charAt(0).toUpperCase()}${id.slice(1)}`;
  const translated = t(key);
  if (translated !== key) return translated;
  return catalog?.providers.find((item) => item.id === id)?.label ?? id;
}

function packLabel(id: string, t: (key: string) => string) {
  const key = `account.pack${id.charAt(0).toUpperCase()}${id.slice(1)}`;
  const label = t(key);
  return label === key ? id : label;
}

function AccountPageInner() {
  const { t, locale } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
  });
  const credits = useQuery({
    queryKey: ["credits"],
    queryFn: () => apiFetch<CreditBalance>("/api/v1/billing/credits"),
  });
  const catalog = useQuery({
    queryKey: ["billing-catalog"],
    queryFn: () => apiFetch<BillingCatalog>("/api/v1/billing/catalog"),
  });
  const orders = useQuery({
    queryKey: ["billing-orders"],
    queryFn: () => apiFetch<PaymentOrder[]>("/api/v1/billing/orders"),
  });
  const transactions = useQuery({
    queryKey: ["billing-transactions"],
    queryFn: () => apiFetch<CreditTransaction[]>("/api/v1/billing/transactions"),
  });

  const canBuy = canCreateContent(me.data);

  useEffect(() => {
    if (me.data?.full_name) setName(me.data.full_name);
  }, [me.data?.full_name]);

  useEffect(() => {
    const payment = searchParams.get("payment");
    if (payment === "success") setNotice(t("account.paymentSuccess"));
    if (payment === "cancel") setNotice(t("account.paymentCancel"));
  }, [searchParams, t]);

  const saveProfile = useMutation({
    mutationFn: () => apiFetch<User>("/api/v1/auth/me", { method: "PATCH", body: { full_name: name } }),
    onSuccess: (user) => {
      queryClient.setQueryData(["me"], user);
      setNotice(t("account.saved"));
      setActionError(null);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const savePassword = useMutation({
    mutationFn: () => {
      if (password !== confirm) {
        throw new Error(t("account.passwordMismatch"));
      }
      return apiFetch<User>("/api/v1/auth/me", {
        method: "PATCH",
        body: { current_password: currentPassword, password },
      });
    },
    onSuccess: () => {
      setCurrentPassword("");
      setPassword("");
      setConfirm("");
      setNotice(t("account.saved"));
      setActionError(null);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const saveCountry = useMutation({
    mutationFn: (billing_country: string) =>
      apiFetch<BillingCatalog>("/api/v1/billing/country", { method: "PATCH", body: { billing_country } }),
    onSuccess: (data) => {
      queryClient.setQueryData(["billing-catalog"], data);
      setActionError(null);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const checkout = useMutation({
    mutationFn: (input: { pack_id: string; provider: string }) =>
      apiFetch<PaymentOrder>("/api/v1/billing/checkout", { method: "POST", body: input }),
    onSuccess: async (order) => {
      if (order.provider === "simulated") {
        const completed = await apiFetch<PaymentOrder>(`/api/v1/billing/orders/${order.id}/simulate`, {
          method: "POST",
        });
        void queryClient.invalidateQueries({ queryKey: ["credits"] });
        void queryClient.invalidateQueries({ queryKey: ["billing-orders"] });
        void queryClient.invalidateQueries({ queryKey: ["billing-transactions"] });
        if (completed.status === "completed") setNotice(t("account.paymentSuccess"));
        return;
      }
      if (order.checkout_url) window.location.assign(order.checkout_url);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  useEffect(() => {
    const payment = searchParams.get("payment");
    const orderId = searchParams.get("order");
    if (payment !== "simulate" || !orderId) return;
    void (async () => {
      try {
        await apiFetch<PaymentOrder>(`/api/v1/billing/orders/${orderId}/simulate`, { method: "POST" });
        setNotice(t("account.paymentSuccess"));
        void queryClient.invalidateQueries({ queryKey: ["credits"] });
        void queryClient.invalidateQueries({ queryKey: ["billing-orders"] });
        void queryClient.invalidateQueries({ queryKey: ["billing-transactions"] });
        router.replace("/account?payment=success");
      } catch (error) {
        setActionError(error instanceof Error ? error.message : t("error.unexpected"));
      }
    })();
  }, [queryClient, router, searchParams, t]);

  const loadError = me.error ?? credits.error ?? catalog.error ?? orders.error ?? transactions.error;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("account.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("account.subtitle")}</p>
      </div>

      {notice ? <p className="text-sm text-accent">{notice}</p> : null}
      {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}

      {loadError ? (
        <ErrorState title={t("account.loadError")} error={loadError} onRetry={() => void me.refetch()} />
      ) : null}

      <Card>
        <CardTitle>{t("account.profile")}</CardTitle>
        <CardDescription>{t("account.profileBody")}</CardDescription>
        {me.isLoading ? (
          <Loader label={t("common.loading")} className="mt-4" />
        ) : (
          <form
            className="mt-4 max-w-md space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              saveProfile.mutate();
            }}
          >
            <div className="space-y-1">
              <Label htmlFor="full_name">{t("common.name")}</Label>
              <Input id="full_name" value={name} onChange={(event) => setName(event.target.value)} required />
            </div>
            <div className="space-y-1">
              <Label htmlFor="email">{t("common.email")}</Label>
              <Input id="email" value={me.data?.email ?? ""} disabled />
            </div>
            <Button type="submit" loading={saveProfile.isPending}>
              {saveProfile.isPending ? t("account.saving") : t("account.saveProfile")}
            </Button>
          </form>
        )}
      </Card>

      <Card>
        <CardTitle>{t("account.password")}</CardTitle>
        <form
          className="mt-4 max-w-md space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            savePassword.mutate();
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="current_password">{t("account.currentPassword")}</Label>
            <Input
              id="current_password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="new_password">{t("account.newPassword")}</Label>
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              required
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="confirm_password">{t("account.confirmPassword")}</Label>
            <Input
              id="confirm_password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(event) => setConfirm(event.target.value)}
              minLength={8}
              required
            />
          </div>
          <Button type="submit" loading={savePassword.isPending}>
            {savePassword.isPending ? t("account.saving") : t("account.changePassword")}
          </Button>
        </form>
      </Card>

      <Card>
        <CardTitle>{t("account.creditsTitle")}</CardTitle>
        <div className="mt-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          {credits.isLoading ? (
            <Skeleton className="h-10 w-28" />
          ) : (
            <p className="text-4xl font-semibold tracking-tight text-accent tabular-nums">
              {credits.data?.balance ?? "—"}
            </p>
          )}
          <p className="text-sm font-medium text-foreground">
            {(credits.data?.balance ?? 0) === 1 ? t("common.credit") : t("common.credits")}
          </p>
        </div>
        <CardDescription className="mt-2">{t("account.creditsBody")}</CardDescription>
        {canBuy ? (
          <label className="mt-4 block max-w-xs">
            <span className="mb-1 block text-sm font-medium">{t("account.country")}</span>
            <select
              className="h-10 w-full rounded-md border border-border bg-card px-3 text-sm"
              value={catalog.data?.billing_country ?? "CO"}
              onChange={(event) => saveCountry.mutate(event.target.value)}
              disabled={saveCountry.isPending}
            >
              {COUNTRIES.map((code) => (
                <option key={code} value={code}>
                  {code}
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-muted-foreground">{t("account.countryHint")}</p>
          </label>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">{t("account.memberHint")}</p>
        )}
      </Card>

      {canBuy ? (
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{t("account.buy")}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{t("account.buyBody")}</p>
          {catalog.isLoading ? (
            <Loader label={t("common.loading")} className="mt-4" />
          ) : !catalog.data?.providers.length ? (
            <p className="mt-4 text-sm text-muted-foreground">{t("account.noProviders")}</p>
          ) : (
            <div className="mt-4 grid gap-4 lg:grid-cols-3">
              {catalog.data.packs.map((pack) => (
                <Card key={pack.id}>
                  <CardTitle>{packLabel(pack.id, t)}</CardTitle>
                  <CardDescription>{t("account.creditsCount", { count: pack.credits })}</CardDescription>
                  <div className="mt-4 space-y-2">
                    {pack.prices.map((price) => {
                      const provider = catalog.data?.providers.find((item) => item.id === price.provider);
                      return (
                        <Button
                          key={`${pack.id}-${price.provider}`}
                          type="button"
                          variant={provider?.recommended ? "primary" : "outline"}
                          className="w-full justify-between"
                          loading={
                            checkout.isPending &&
                            checkout.variables?.pack_id === pack.id &&
                            checkout.variables?.provider === price.provider
                          }
                          onClick={() => checkout.mutate({ pack_id: pack.id, provider: price.provider })}
                        >
                          <span>
                            {t("account.payWith", { provider: providerLabel(price.provider, t, catalog.data) })}
                            {provider?.recommended ? ` · ${t("account.recommended")}` : ""}
                          </span>
                          <span>{formatMoney(price.amount, price.currency, locale)}</span>
                        </Button>
                      );
                    })}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>
      ) : null}

      <Card>
        <CardTitle>{t("account.orders")}</CardTitle>
        {orders.isLoading ? (
          <Loader label={t("common.loading")} className="mt-4" />
        ) : orders.data?.length ? (
          <ul className="mt-4 divide-y divide-border">
            {orders.data.map((order) => (
              <li key={order.id} className="flex flex-wrap items-center justify-between gap-2 py-3">
                <div>
                  <p className="text-sm font-medium">
                    {packLabel(order.pack_id, t)} · {providerLabel(order.provider, t, catalog.data)}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {t("account.creditsCount", { count: order.credits })} ·{" "}
                    {formatMoney(order.amount, order.currency, locale)} · {formatDateTime(order.created_at, locale)}
                  </p>
                </div>
                <Badge>{t(`account.status${order.status.charAt(0).toUpperCase()}${order.status.slice(1)}`)}</Badge>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">{t("account.noOrders")}</p>
        )}
      </Card>

      <Card>
        <CardTitle>{t("account.movements")}</CardTitle>
        {transactions.isLoading ? (
          <Loader label={t("common.loading")} className="mt-4" />
        ) : transactions.data?.length ? (
          <ul className="mt-4 divide-y divide-border">
            {transactions.data.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-3 text-sm">
                <span>
                  {item.reason} · {formatDateTime(item.created_at, locale)}
                </span>
                <span className={item.amount > 0 ? "text-accent" : "text-muted-foreground"}>
                  {item.amount > 0 ? "+" : ""}
                  {item.amount}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-muted-foreground">{t("account.noMovements")}</p>
        )}
      </Card>
    </div>
  );
}

export default function AccountPage() {
  return (
    <Suspense fallback={<PageLoader />}>
      <AccountPageInner />
    </Suspense>
  );
}
