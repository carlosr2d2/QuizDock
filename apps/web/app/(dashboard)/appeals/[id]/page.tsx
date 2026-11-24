"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AppealThread } from "@/components/appeal-thread";
import { ChunkPicker } from "@/components/chunk-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { PageLoader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { formatDateTime } from "@/lib/utils";
import type { AppealDetail, DocumentChunkPreview } from "@/types/api";

export default function AppealDetailPage() {
  const { t, locale } = useI18n();
  const params = useParams<{ id: string }>();
  const appealId = params.id;
  const queryClient = useQueryClient();
  const [quote, setQuote] = useState("");
  const [chunkId, setChunkId] = useState("");
  const [argument, setArgument] = useState("");

  const detail = useQuery({
    queryKey: ["appeals", appealId],
    queryFn: () => apiFetch<AppealDetail>(`/api/v1/appeals/${appealId}`),
  });

  const canAttach =
    detail.data?.status === "needs_info" ||
    detail.data?.status === "pending" ||
    detail.data?.status === "in_review";
  const documentId =
    detail.data?.document_id ||
    (typeof detail.data?.system_evidence_snapshot?.document_id === "string"
      ? detail.data.system_evidence_snapshot.document_id
      : null);

  const chunks = useQuery({
    queryKey: ["document-chunks", documentId],
    queryFn: () => apiFetch<DocumentChunkPreview[]>(`/api/v1/documents/${documentId}/chunks?limit=100`),
    enabled: Boolean(documentId) && Boolean(canAttach),
  });

  const addEvidence = useMutation({
    mutationFn: () =>
      apiFetch<AppealDetail>(`/api/v1/appeals/${appealId}/evidence`, {
        method: "POST",
        body: {
          quote: quote.trim() || undefined,
          chunk_id: chunkId || undefined,
          argument: argument.trim() || undefined,
        },
      }),
    onSuccess: async () => {
      setQuote("");
      setChunkId("");
      setArgument("");
      await queryClient.invalidateQueries({ queryKey: ["appeals", appealId] });
      await queryClient.invalidateQueries({ queryKey: ["appeals", "mine"] });
    },
  });

  function selectChunk(nextId: string, chunk: DocumentChunkPreview | null) {
    setChunkId(nextId);
    if (chunk) {
      setQuote(chunk.content.slice(0, 900));
    } else if (!nextId) {
      setQuote("");
    }
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
  const snapshotQuote =
    typeof item.system_evidence_snapshot.quote === "string" ? item.system_evidence_snapshot.quote : null;

  return (
    <div className="space-y-8">
      <div>
        <Link href="/appeals" className="text-sm text-muted-foreground underline-offset-4 hover:underline">
          {t("appeals.backList")}
        </Link>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight">{item.exam_title}</h1>
          <Badge>{t(`appeals.status.${item.status}`)}</Badge>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">{formatDateTime(item.created_at, locale)}</p>
      </div>

      <section className="space-y-2 rounded-xl border border-border bg-card p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.question")}</p>
        <p className="text-sm text-foreground">{item.question_prompt}</p>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.argument")}</p>
        <p className="text-sm text-foreground">{item.student_argument}</p>
      </section>

      {snapshotQuote ? (
        <section className="space-y-2 rounded-xl border border-border bg-card p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("appeals.systemSnapshot")}
          </p>
          <blockquote className="border-l-2 border-accent/40 pl-3 text-sm italic text-foreground/90">
            {snapshotQuote}
          </blockquote>
        </section>
      ) : null}

      <section className="space-y-3 rounded-xl border border-border bg-card p-5">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.evidence")}</p>
        {item.evidence.length ? (
          <ul className="space-y-3">
            {item.evidence.map((row) => (
              <li key={row.id} className="rounded-lg border border-border/70 bg-background/60 p-3">
                <p className="text-xs text-muted-foreground">{row.source}</p>
                <blockquote className="mt-1 text-sm italic">{row.quote}</blockquote>
                {row.argument ? <p className="mt-2 text-sm text-muted-foreground">{row.argument}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">{t("appeals.noEvidence")}</p>
        )}

        {canAttach ? (
          <div className="space-y-3 border-t border-border pt-3">
            <p className="text-xs text-muted-foreground">{t("appeals.attachChunkHint")}</p>
            {documentId ? (
              <ChunkPicker
                chunks={chunks.data ?? []}
                value={chunkId}
                onChange={selectChunk}
                loading={chunks.isLoading}
              />
            ) : (
              <p className="text-xs text-muted-foreground">{t("appeals.noChunks")}</p>
            )}
            <label className="block space-y-1">
              <span className="text-xs font-medium text-foreground">{t("appeals.quoteLabel")}</span>
              <textarea
                className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                value={quote}
                onChange={(event) => setQuote(event.target.value)}
                placeholder={t("appeals.quotePlaceholder")}
              />
            </label>
            <textarea
              className="min-h-16 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              value={argument}
              onChange={(event) => setArgument(event.target.value)}
              placeholder={t("appeals.argumentPlaceholder")}
            />
            {addEvidence.error ? <p className="text-sm text-destructive">{addEvidence.error.message}</p> : null}
            <Button
              type="button"
              size="sm"
              loading={addEvidence.isPending}
              disabled={!(quote.trim().length >= 8 || chunkId)}
              onClick={() => addEvidence.mutate()}
            >
              {t("appeals.attachChunk")}
            </Button>
          </div>
        ) : null}
      </section>

      {item.resolution ? (
        <section className="space-y-2 rounded-xl border border-border bg-card p-5">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{t("appeals.resolution")}</p>
          <Badge>{t(`appeals.status.${item.resolution.decision}`)}</Badge>
          <p className="text-sm text-foreground">{item.resolution.rationale}</p>
        </section>
      ) : null}

      <AppealThread appealId={appealId} detail={item} canComment={item.status !== "closed"} />

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
