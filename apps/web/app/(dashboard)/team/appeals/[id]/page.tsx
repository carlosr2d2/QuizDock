"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AppealAiCard } from "@/components/appeal-ai-card";
import { AppealThread } from "@/components/appeal-thread";
import { PersonalWorkspaceHint } from "@/components/team/personal-workspace-hint";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { PageLoader } from "@/components/ui/loader";
import { apiDownload, apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { useTeamPage } from "@/lib/use-team-page";
import { formatDateTime } from "@/lib/utils";
import type { AppealDetail } from "@/types/api";

export default function TeamAppealDetailPage() {
  const { t, locale } = useI18n();
  const params = useParams<{ id: string }>();
  const appealId = params.id;
  const { me, snapshot, isPersonal } = useTeamPage();
  const canResolve = snapshot?.role === "owner" || snapshot?.role === "admin";
  const canExport =
    snapshot?.role === "owner" || snapshot?.role === "admin" || snapshot?.role === "auditor";
  const queryClient = useQueryClient();
  const [rationale, setRationale] = useState("");

  const detail = useQuery({
    queryKey: ["appeals", appealId],
    queryFn: () => apiFetch<AppealDetail>(`/api/v1/appeals/${appealId}`),
    enabled: !isPersonal,
    refetchInterval: (query) => {
      const status = query.state.data?.ai_recommendation?.status;
      return status === "queued" || status === "running" ? 1500 : false;
    },
  });

  const markReview = useMutation({
    mutationFn: () =>
      apiFetch<AppealDetail>(`/api/v1/appeals/${appealId}/status`, {
        method: "PATCH",
        body: { status: "in_review" },
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appeals", appealId] });
      await queryClient.invalidateQueries({ queryKey: ["appeals", "inbox"] });
    },
  });

  const resolve = useMutation({
    mutationFn: (decision: "accepted" | "rejected" | "needs_info") =>
      apiFetch<AppealDetail>(`/api/v1/appeals/${appealId}/resolve`, {
        method: "POST",
        body: { decision, rationale },
      }),
    onSuccess: async () => {
      setRationale("");
      await queryClient.invalidateQueries({ queryKey: ["appeals", appealId] });
      await queryClient.invalidateQueries({ queryKey: ["appeals", "inbox"] });
    },
  });

  const exportJson = useMutation({
    mutationFn: async () => {
      const blob = await apiDownload(`/api/v1/appeals/${appealId}/export`);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `appeal-${appealId}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
    },
  });

  if (isPersonal) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold tracking-tight">{t("appeals.inboxTitle")}</h1>
        <PersonalWorkspaceHint user={me.data} actionLabel={t("team.goTeam")} />
      </div>
    );
  }

  if (detail.isLoading) {
    return <PageLoader label={t("appeals.loadingDetail")} />;
  }
  if (detail.error || !detail.data) {
    return (
      <ErrorState
        title={t("appeals.detailError")}
        error={detail.error ?? new Error(t("appeals.detailError"))}
        onRetry={() => void detail.refetch()}
      />
    );
  }

  const item = detail.data;
  const open = item.status === "pending" || item.status === "in_review" || item.status === "needs_info";
  const snapshotQuote =
    typeof item.system_evidence_snapshot.quote === "string" ? item.system_evidence_snapshot.quote : null;

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/team/appeals"
          className="text-sm text-muted-foreground underline-offset-4 hover:underline"
        >
          {t("appeals.backList")}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{item.exam_title}</h1>
          <Badge>{t(`appeals.status.${item.status}`)}</Badge>
          {canExport ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              loading={exportJson.isPending}
              onClick={() => exportJson.mutate()}
            >
              {exportJson.isPending ? t("appeals.exporting") : t("appeals.exportJson")}
            </Button>
          ) : null}
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {t("appeals.student")}: {item.student_name || item.student_email} ·{" "}
          {formatDateTime(item.created_at, locale)}
        </p>
        {exportJson.error ? <p className="mt-2 text-sm text-destructive">{exportJson.error.message}</p> : null}
      </div>

      <section className="space-y-2 rounded-xl border border-border bg-card p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.question")}</p>
        <p className="text-sm">{item.question_prompt}</p>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.argument")}</p>
        <p className="text-sm">{item.student_argument}</p>
      </section>

      {canResolve || snapshot?.role === "auditor" ? (
        <AppealAiCard appealId={appealId} detail={item} canRequest={canResolve && open} />
      ) : null}

      {snapshotQuote ? (
        <section className="space-y-2 rounded-xl border border-border bg-card p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("appeals.systemSnapshot")}
          </p>
          <blockquote className="border-l-2 border-accent/40 pl-3 text-sm italic">{snapshotQuote}</blockquote>
        </section>
      ) : null}

      <section className="space-y-3 rounded-xl border border-border bg-card p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.evidence")}</p>
        {item.evidence.length ? (
          <ul className="space-y-3">
            {item.evidence.map((row) => (
              <li key={row.id} className="rounded-lg border border-border/70 p-3">
                <p className="text-xs text-muted-foreground">{row.source}</p>
                <blockquote className="mt-1 text-sm italic">{row.quote}</blockquote>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t("appeals.noEvidence")}</p>
        )}
      </section>

      {item.resolution ? (
        <section className="space-y-2 rounded-xl border border-border bg-card p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.resolution")}</p>
          <Badge>{t(`appeals.status.${item.resolution.decision}`)}</Badge>
          <p className="text-sm">{item.resolution.rationale}</p>
        </section>
      ) : null}

      {canResolve && open ? (
        <section className="space-y-3 rounded-xl border border-border bg-card p-5">
          <p className="text-sm font-medium">{t("appeals.resolve")}</p>
          <textarea
            className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={rationale}
            onChange={(event) => setRationale(event.target.value)}
            placeholder={t("appeals.rationalePlaceholder")}
          />
          {item.status === "pending" ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              loading={markReview.isPending}
              onClick={() => markReview.mutate()}
            >
              {t("appeals.markReview")}
            </Button>
          ) : null}
          {item.ai_recommendation?.status === "ready" && item.ai_recommendation.recommendation ? (
            <Button
              type="button"
              size="sm"
              variant="secondary"
              onClick={() => {
                if (!rationale.trim() && item.ai_recommendation?.rationale) {
                  setRationale(item.ai_recommendation.rationale);
                }
              }}
            >
              {t("appeals.aiUseRationale")}
            </Button>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              loading={resolve.isPending}
              disabled={rationale.trim().length < 4}
              onClick={() => resolve.mutate("accepted")}
            >
              {t("appeals.accept")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="destructive"
              loading={resolve.isPending}
              disabled={rationale.trim().length < 4}
              onClick={() => resolve.mutate("rejected")}
            >
              {t("appeals.reject")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              loading={resolve.isPending}
              disabled={rationale.trim().length < 4}
              onClick={() => resolve.mutate("needs_info")}
            >
              {t("appeals.needsInfo")}
            </Button>
          </div>
          {resolve.error ? <p className="text-sm text-destructive">{resolve.error.message}</p> : null}
          {markReview.error ? <p className="text-sm text-destructive">{markReview.error.message}</p> : null}
        </section>
      ) : null}

      {!canResolve && snapshot?.role !== "auditor" ? (
        <p className="text-sm text-muted-foreground">{t("appeals.forbidden")}</p>
      ) : null}

      <AppealThread
        appealId={appealId}
        detail={item}
        canComment={canResolve && item.status !== "closed"}
      />

      <section className="space-y-2 rounded-xl border border-border bg-card p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.history")}</p>
        <ul className="space-y-2">
          {item.actions.map((action) => (
            <li key={action.id} className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{action.action}</span>
              {" · "}
              {formatDateTime(action.created_at, locale)}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
