"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ChunkPicker } from "@/components/chunk-picker";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { Appeal, AppealDetail, DocumentChunkPreview } from "@/types/api";

type AppealCtaProps = {
  attemptId: string;
  questionId: string;
  documentId: string | null | undefined;
  existing?: Appeal | null;
  className?: string;
};

export function AppealCta({ attemptId, questionId, documentId, existing, className }: AppealCtaProps) {
  const t = useT();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [argument, setArgument] = useState("");
  const [chunkId, setChunkId] = useState<string>("");
  const [quote, setQuote] = useState("");

  const chunks = useQuery({
    queryKey: ["document-chunks", documentId],
    queryFn: () => apiFetch<DocumentChunkPreview[]>(`/api/v1/documents/${documentId}/chunks?limit=100`),
    enabled: Boolean(documentId) && open && !existing,
  });

  const create = useMutation({
    mutationFn: () =>
      apiFetch<AppealDetail>("/api/v1/appeals", {
        method: "POST",
        body: {
          attempt_id: attemptId,
          question_id: questionId,
          argument,
          evidence_quote: quote.trim() || undefined,
          evidence_chunk_id: chunkId || undefined,
        },
      }),
    onSuccess: async () => {
      setOpen(false);
      setArgument("");
      setQuote("");
      setChunkId("");
      await queryClient.invalidateQueries({ queryKey: ["appeals"] });
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

  if (existing) {
    return (
      <div className={cn("mt-3 rounded-lg border border-border/70 bg-background/60 px-3 py-2", className)}>
        <p className="text-xs font-medium text-foreground">
          {t("appeals.statusLabel", { status: t(`appeals.status.${existing.status}`) })}
        </p>
        <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{existing.student_argument}</p>
        <a href={`/appeals/${existing.id}`} className="mt-2 inline-block text-xs underline-offset-4 hover:underline">
          {t("appeals.viewMine")}
        </a>
      </div>
    );
  }

  return (
    <div className={cn("mt-3", className)}>
      {!open ? (
        <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
          {t("appeals.disagree")}
        </Button>
      ) : (
        <div className="space-y-3 rounded-lg border border-border bg-card p-3">
          <p className="text-sm font-medium text-foreground">{t("appeals.formTitle")}</p>
          <p className="text-xs text-muted-foreground">{t("appeals.formHint")}</p>
          <textarea
            className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={argument}
            onChange={(event) => setArgument(event.target.value)}
            placeholder={t("appeals.argumentPlaceholder")}
            maxLength={4000}
          />
          {documentId ? (
            <div className="space-y-2">
              <p className="text-xs font-medium text-foreground">{t("appeals.attachChunk")}</p>
              <p className="text-xs text-muted-foreground">{t("appeals.attachChunkHint")}</p>
              <ChunkPicker
                chunks={chunks.data ?? []}
                value={chunkId}
                onChange={selectChunk}
                loading={chunks.isLoading}
              />
              <label className="block space-y-1">
                <span className="text-xs font-medium text-foreground">{t("appeals.quoteLabel")}</span>
                <textarea
                  className="min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  value={quote}
                  onChange={(event) => setQuote(event.target.value)}
                  placeholder={t("appeals.quotePlaceholder")}
                  maxLength={2000}
                />
              </label>
            </div>
          ) : null}
          {create.error ? <p className="text-sm text-destructive">{create.error.message}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              loading={create.isPending}
              disabled={argument.trim().length < 8}
              onClick={() => create.mutate()}
            >
              {create.isPending ? t("appeals.submitting") : t("appeals.submit")}
            </Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpen(false)} disabled={create.isPending}>
              {t("common.cancel")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
