"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { AppealAiRecommendation, AppealDetail } from "@/types/api";

type AppealAiCardProps = {
  appealId: string;
  detail: AppealDetail;
  canRequest: boolean;
};

export function AppealAiCard({ appealId, detail, canRequest }: AppealAiCardProps) {
  const t = useT();
  const queryClient = useQueryClient();
  const recommendation = detail.ai_recommendation;

  const request = useMutation({
    mutationFn: () =>
      apiFetch<AppealAiRecommendation>(`/api/v1/appeals/${appealId}/ai-review`, {
        method: "POST",
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["appeals", appealId] });
    },
  });

  const pending =
    recommendation?.status === "queued" || recommendation?.status === "running" || request.isPending;

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("appeals.aiTitle")}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">{t("appeals.aiHint")}</p>
        </div>
        {canRequest ? (
          <Button
            type="button"
            size="sm"
            variant="outline"
            loading={pending}
            disabled={pending}
            onClick={() => request.mutate()}
          >
            {pending ? t("appeals.aiRunning") : recommendation ? t("appeals.aiRerun") : t("appeals.aiRequest")}
          </Button>
        ) : null}
      </div>

      <EvidenceCompare detail={detail} recommendation={recommendation} />

      {request.error ? <p className="text-sm text-destructive">{request.error.message}</p> : null}

      {recommendation?.status === "failed" ? (
        <p className="text-sm text-destructive">
          {recommendation.error_message || t("appeals.aiFailed")}
        </p>
      ) : null}

      {recommendation?.status === "ready" ? (
        <div className="space-y-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>
              {t(`appeals.status.${recommendation.recommendation || "needs_info"}`)}
            </Badge>
            {recommendation.ambiguity ? <Badge>{t("appeals.aiAmbiguity")}</Badge> : null}
            {recommendation.confidence != null ? (
              <span className="text-xs text-muted-foreground">
                {t("appeals.aiConfidence", {
                  percent: Math.round(Math.max(0, Math.min(1, recommendation.confidence)) * 100),
                })}
              </span>
            ) : null}
          </div>
          <p className="text-sm text-foreground">{recommendation.rationale}</p>
          <p className="text-xs text-muted-foreground">{t("appeals.aiNonBinding")}</p>
        </div>
      ) : null}

      {pending && !recommendation?.rationale ? (
        <p className="text-sm text-muted-foreground">{t("appeals.aiPendingBody")}</p>
      ) : null}
    </section>
  );
}

function EvidenceCompare({
  detail,
  recommendation,
}: {
  detail: AppealDetail;
  recommendation?: AppealAiRecommendation | null;
}) {
  const t = useT();
  const systemQuote =
    recommendation?.system_quote ||
    (typeof detail.system_evidence_snapshot.quote === "string"
      ? detail.system_evidence_snapshot.quote
      : null);
  const studentQuote =
    recommendation?.student_quote || detail.evidence.find((item) => item.quote)?.quote || null;

  return (
    <div className="grid gap-3 md:grid-cols-2">
      <QuoteColumn
        title={t("appeals.aiSystemEvidence")}
        quote={systemQuote}
        empty={t("appeals.aiNoSystemEvidence")}
        tone="system"
      />
      <QuoteColumn
        title={t("appeals.aiStudentEvidence")}
        quote={studentQuote}
        empty={t("appeals.aiNoStudentEvidence")}
        tone="student"
      />
    </div>
  );
}

function QuoteColumn({
  title,
  quote,
  empty,
  tone,
}: {
  title: string;
  quote: string | null;
  empty: string;
  tone: "system" | "student";
}) {
  return (
    <div
      className={cn(
        "rounded-lg border p-3",
        tone === "system" ? "border-border bg-background/70" : "border-accent/20 bg-accent/5",
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</p>
      {quote ? (
        <blockquote className="mt-2 whitespace-pre-wrap text-sm italic leading-snug text-foreground">
          {quote}
        </blockquote>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}
