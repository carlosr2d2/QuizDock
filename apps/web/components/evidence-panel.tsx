"use client";

import type { Locale } from "@/lib/i18n/config";
import { useT } from "@/lib/i18n/provider";
import { cn, formatDateTime } from "@/lib/utils";
import type { Evidence } from "@/types/api";

type EvidencePanelProps = {
  evidence: Evidence | null | undefined;
  explanation?: string | null;
  locale: Locale;
  className?: string;
};

export function EvidencePanel({ evidence, explanation, locale, className }: EvidencePanelProps) {
  const t = useT();
  const hasExplanation = Boolean(explanation?.trim());
  const hasEvidence = Boolean(evidence?.quote?.trim());

  if (!hasExplanation && !hasEvidence) {
    return (
      <div className={cn("mt-3 rounded-lg border border-border/70 bg-background/60 px-3 py-2", className)}>
        <p className="text-xs text-muted-foreground">{t("exams.evidenceUnavailable")}</p>
      </div>
    );
  }

  const pageLabel = formatPages(evidence?.page_start, evidence?.page_end, t("exams.pageUnavailable"));
  const confidence =
    evidence?.confidence != null ? Math.round(Math.max(0, Math.min(1, evidence.confidence)) * 100) : null;

  return (
    <div className={cn("mt-3 space-y-3 rounded-lg border border-border/70 bg-background/70 p-3", className)}>
      {hasExplanation ? (
        <section>
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {t("exams.aiJustification")}
          </p>
          <p className="mt-1 text-sm text-foreground min-w-0 break-words [overflow-wrap:anywhere]">
            {explanation}
          </p>
        </section>
      ) : null}

      {hasEvidence ? (
        <>
          <section>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {t("exams.documentaryEvidence")}
            </p>
            <blockquote className="mt-1 border-l-2 border-accent/40 pl-3 text-sm italic text-foreground/90 min-w-0 break-words [overflow-wrap:anywhere]">
              {evidence?.quote}
            </blockquote>
          </section>

          <section className="grid gap-1 text-xs text-muted-foreground sm:grid-cols-2">
            <p>
              <span className="font-medium text-foreground/80">{t("exams.evidenceDocument")}: </span>
              {evidence?.document_title?.trim() || t("exams.evidenceDocumentUnknown")}
            </p>
            <p>
              <span className="font-medium text-foreground/80">{t("exams.evidencePage")}: </span>
              {pageLabel}
            </p>
            {evidence?.chapter ? (
              <p>
                <span className="font-medium text-foreground/80">{t("exams.evidenceChapter")}: </span>
                {evidence.chapter}
              </p>
            ) : null}
            {evidence?.section ? (
              <p>
                <span className="font-medium text-foreground/80">{t("exams.evidenceSection")}: </span>
                {evidence.section}
              </p>
            ) : null}
            {confidence != null ? (
              <p>
                <span className="font-medium text-foreground/80">{t("exams.evidenceConfidence")}: </span>
                {t("common.percent", { percent: confidence })}
              </p>
            ) : null}
            {evidence?.generated_at ? (
              <p>
                <span className="font-medium text-foreground/80">{t("exams.evidenceGeneratedAt")}: </span>
                {formatDateTime(evidence.generated_at, locale)}
              </p>
            ) : null}
          </section>
        </>
      ) : (
        <p className="text-xs text-muted-foreground">{t("exams.evidenceUnavailable")}</p>
      )}
    </div>
  );
}

function formatPages(
  pageStart: number | null | undefined,
  pageEnd: number | null | undefined,
  unavailable: string,
): string {
  if (pageStart == null) {
    return unavailable;
  }
  if (pageEnd != null && pageEnd !== pageStart) {
    return `${pageStart}–${pageEnd}`;
  }
  return String(pageStart);
}
