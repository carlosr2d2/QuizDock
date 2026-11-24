"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, PageLoader } from "@/components/ui/loader";
import { surfaceListClass } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";
import { formatDateTime } from "@/lib/utils";
import type { Locale } from "@/lib/i18n/config";
import type {
  AiDecisionEvent,
  AiDecisionEventList,
  AuditEvent,
  AuditEventList,
} from "@/types/api";

const PAGE_SIZE = 50;

export default function TeamAuditPage() {
  const { t, locale } = useI18n();
  const { me, team, snapshot, isPersonal } = useTeamPage();
  const queryClient = useQueryClient();
  const canView =
    snapshot?.role === "owner" || snapshot?.role === "admin" || snapshot?.role === "auditor";
  const canPurge = snapshot?.role === "owner" || snapshot?.role === "admin";
  const [tab, setTab] = useState<"workspace" | "ai">("workspace");
  const [feature, setFeature] = useState<string>("");

  const log = useQuery({
    queryKey: ["team-audit"],
    queryFn: () =>
      apiFetch<AuditEventList>(`/api/v1/organizations/current/audit?limit=${PAGE_SIZE}&offset=0`),
    enabled: Boolean(snapshot) && !isPersonal && canView && tab === "workspace",
  });

  const aiLog = useQuery({
    queryKey: ["team-audit-ai", feature],
    queryFn: () =>
      apiFetch<AiDecisionEventList>(
        `/api/v1/organizations/current/audit/ai?limit=${PAGE_SIZE}&offset=0${
          feature ? `&feature=${encodeURIComponent(feature)}` : ""
        }`,
      ),
    enabled: Boolean(snapshot) && !isPersonal && canView && tab === "ai",
  });

  const purge = useMutation({
    mutationFn: () =>
      apiFetch<{ deleted: number; retention_days: number }>(
        "/api/v1/organizations/current/audit/ai/purge",
        { method: "POST" },
      ),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["team-audit-ai"] });
    },
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("team.auditTitle")}</h1>
        {team.isLoading ? (
          <Loader label={t("common.loadingWorkspace")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {isPersonal
              ? t("team.auditPersonal")
              : t("team.auditBody", { name: snapshot?.organization.name ?? t("team.thisWorkspace") })}
          </p>
        )}
      </div>

      {team.isLoading ? <PageLoader label={t("team.loadingAudit")} /> : null}
      {team.isError ? (
        <ErrorState
          title={t("team.loadTeamError")}
          error={team.error}
          onRetry={() => void team.refetch()}
        />
      ) : null}

      {isPersonal ? <PersonalWorkspaceHint user={me.data} actionLabel={t("team.goTeam")} /> : null}
      {!isPersonal && snapshot && !canView ? (
        <p className="text-sm text-muted-foreground">{t("team.auditForbidden")}</p>
      ) : null}

      {!isPersonal && canView ? (
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setTab("workspace")}
            className={`rounded-md border px-3 py-1.5 text-sm ${
              tab === "workspace"
                ? "border-accent bg-accent/10 text-foreground"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            {t("team.auditTabWorkspace")}
          </button>
          <button
            type="button"
            onClick={() => setTab("ai")}
            className={`rounded-md border px-3 py-1.5 text-sm ${
              tab === "ai"
                ? "border-accent bg-accent/10 text-foreground"
                : "border-border text-muted-foreground hover:bg-muted"
            }`}
          >
            {t("team.auditTabAi")}
          </button>
        </div>
      ) : null}

      {tab === "workspace" ? (
        <>
          {log.isLoading ? <PageLoader label={t("team.loadingAudit")} /> : null}
          {log.isError ? (
            <ErrorState
              title={t("team.auditError")}
              error={log.error}
              onRetry={() => void log.refetch()}
            />
          ) : null}
          {log.data?.items.length ? (
            <AuditList items={log.data.items} locale={locale} />
          ) : log.data ? (
            <EmptyState title={t("team.auditEmpty")} description={t("team.auditEmptyBody")} />
          ) : null}
        </>
      ) : null}

      {tab === "ai" ? (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            {[
              { value: "", label: t("appeals.filterAll") },
              { value: "generation", label: t("team.aiFeature.generation") },
              { value: "evidence", label: t("team.aiFeature.evidence") },
              { value: "chat", label: t("team.aiFeature.chat") },
              { value: "appeal_review", label: t("team.aiFeature.appeal_review") },
            ].map((item) => (
              <button
                key={item.value || "all"}
                type="button"
                onClick={() => setFeature(item.value)}
                className={`rounded-md border px-3 py-1.5 text-sm ${
                  feature === item.value
                    ? "border-accent bg-accent/10 text-foreground"
                    : "border-border text-muted-foreground hover:bg-muted"
                }`}
              >
                {item.label}
              </button>
            ))}
            {canPurge ? (
              <Button
                type="button"
                size="sm"
                variant="outline"
                loading={purge.isPending}
                onClick={() => purge.mutate()}
              >
                {t("team.aiPurge")}
              </Button>
            ) : null}
          </div>
          {purge.data ? (
            <p className="text-xs text-muted-foreground">
              {t("team.aiPurged", { count: purge.data.deleted, days: purge.data.retention_days })}
            </p>
          ) : null}
          {purge.error ? <p className="text-sm text-destructive">{purge.error.message}</p> : null}
          {aiLog.isLoading ? <PageLoader label={t("team.loadingAudit")} /> : null}
          {aiLog.isError ? (
            <ErrorState
              title={t("team.auditError")}
              error={aiLog.error}
              onRetry={() => void aiLog.refetch()}
            />
          ) : null}
          {aiLog.data?.items.length ? (
            <AiAuditList items={aiLog.data.items} locale={locale} />
          ) : aiLog.data ? (
            <EmptyState title={t("team.aiAuditEmpty")} description={t("team.aiAuditEmptyBody")} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function AuditList({ items, locale }: { items: AuditEvent[]; locale: Locale }) {
  const { t } = useI18n();
  return (
    <ul className={surfaceListClass}>
      {items.map((item) => (
        <li
          key={item.id}
          className="flex flex-col gap-1 px-5 py-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6"
        >
          <div className="min-w-0">
            <p className="text-sm font-medium">{actionLabel(item.action, t)}</p>
            <p className="mt-0.5 text-sm text-muted-foreground">{item.summary}</p>
          </div>
          <div className="shrink-0 text-xs text-muted-foreground sm:text-right">
            <p>{item.actor_full_name || item.actor_email || t("team.auditSystem")}</p>
            <p className="mt-0.5">{formatDateTime(item.created_at, locale)}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function AiAuditList({ items, locale }: { items: AiDecisionEvent[]; locale: Locale }) {
  const { t } = useI18n();
  return (
    <ul className={surfaceListClass}>
      {items.map((item) => (
        <li key={item.id} className="space-y-2 px-5 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>{t(`team.aiFeature.${item.feature}`)}</Badge>
            <Badge>{item.outcome || t("team.aiOutcomeUnknown")}</Badge>
            {item.confidence != null ? (
              <span className="text-xs text-muted-foreground">
                {t("appeals.aiConfidence", {
                  percent: Math.round(Math.max(0, Math.min(1, item.confidence)) * 100),
                })}
              </span>
            ) : null}
          </div>
          <p className="text-sm text-muted-foreground">
            {item.model || t("team.aiModelUnknown")}
            {item.prompt_hash ? ` · ${item.prompt_hash.slice(0, 10)}…` : ""}
            {item.chunk_ids?.length ? ` · ${t("team.aiChunks", { count: item.chunk_ids.length })}` : ""}
          </p>
          <div className="text-xs text-muted-foreground">
            {item.actor_full_name || item.actor_email || t("team.auditSystem")} ·{" "}
            {formatDateTime(item.created_at, locale)}
          </div>
        </li>
      ))}
    </ul>
  );
}

function actionLabel(action: string, t: (key: string) => string) {
  const key = `auditAction.${action}`;
  const label = t(key);
  return label === key ? action : label;
}
