"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { BookOpen, Layers, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { DocumentCover } from "@/components/document-cover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle, surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ListLoader, Loader, ProgressBar } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch, apiUpload } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { canCreateContent } from "@/lib/permissions";
import { cn, formatDateTime } from "@/lib/utils";
import type { CreditBalance, Document, Exam, GenerationJob, User } from "@/types/api";

const MIN_QUESTIONS = 1;
const MAX_QUESTIONS = 50;
const CREDIT_PER_QUESTION = 1;
const FLASHCARD_COST = 12;
const QUESTION_PRESETS = [5, 10, 15, 20, 30];

export default function DocumentsPage() {
  const { t, locale } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const router = useRouter();
  const [actionError, setActionError] = useState<string | null>(null);
  const [examDoc, setExamDoc] = useState<Document | null>(null);
  const [questionCount, setQuestionCount] = useState(10);
  const [uploadProgress, setUploadProgress] = useState<{
    filename: string;
    percent: number;
    phase: "uploading" | "processing";
    documentId?: string;
  } | null>(null);

  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => apiFetch<Document[]>("/api/v1/documents"),
    refetchInterval: (query) => {
      const items = query.state.data ?? [];
      return items.some((doc) => doc.status === "uploaded" || doc.status === "processing")
        ? 2500
        : false;
    },
  });
  const credits = useQuery({
    queryKey: ["credits"],
    queryFn: () => apiFetch<CreditBalance>("/api/v1/billing/credits"),
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
  });
  const canAuthor = canCreateContent(me.data);

  const upload = useMutation({
    mutationFn: async (file: File) => {
      setActionError(null);
      setUploadProgress({ filename: file.name, percent: 0, phase: "uploading" });
      const body = new FormData();
      body.append("file", file);
      body.append("language", "auto");
      return apiUpload<Document>("/api/v1/documents", body, (percent) => {
        setUploadProgress((current) =>
          current?.phase === "uploading" ? { ...current, percent } : current,
        );
      });
    },
    onSuccess: (doc) => {
      setUploadProgress({
        filename: doc.title || doc.filename,
        percent: 100,
        phase: "processing",
        documentId: doc.id,
      });
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error: Error) => {
      setUploadProgress(null);
      setActionError(error.message);
    },
  });

  useEffect(() => {
    if (!uploadProgress?.documentId || uploadProgress.phase !== "processing") return;
    const item = documents.data?.find((doc) => doc.id === uploadProgress.documentId);
    if (item && (item.status === "ready" || item.status === "failed")) {
      setUploadProgress(null);
    }
  }, [documents.data, uploadProgress]);

  const generateExam = useMutation({
    mutationFn: ({ documentId, questionCount: count }: { documentId: string; questionCount: number }) =>
      apiFetch<Exam>("/api/v1/exams", {
        method: "POST",
        body: { document_id: documentId, question_count: count },
      }),
    onSuccess: (exam) => {
      setExamDoc(null);
      queryClient.invalidateQueries({ queryKey: ["credits"] });
      queryClient.invalidateQueries({ queryKey: ["exams"] });
      router.push(`/exams/${exam.id}`);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const generateCards = useMutation({
    mutationFn: (documentId: string) =>
      apiFetch<GenerationJob>("/api/v1/flashcards/generate", {
        method: "POST",
        body: { document_id: documentId, card_count: FLASHCARD_COST },
      }),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["credits"] });
      router.push(`/flashcards?job=${job.id}`);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const remove = useMutation({
    mutationFn: (documentId: string) =>
      apiFetch<void>(`/api/v1/documents/${documentId}`, { method: "DELETE" }),
    onSuccess: (_result, documentId) => {
      if (examDoc?.id === documentId) setExamDoc(null);
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const busyId = generateExam.variables?.documentId ?? generateCards.variables ?? remove.variables ?? null;
  const balance = credits.data?.balance ?? 0;
  const examCost = questionCount * CREDIT_PER_QUESTION;
  const examCountValid = questionCount >= MIN_QUESTIONS && questionCount <= MAX_QUESTIONS;
  const canAffordExam = examCountValid && examCost <= balance;
  const canAffordCards = FLASHCARD_COST <= balance;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t("documents.title")}</h1>
          {credits.isLoading ? (
            <Loader label={t("documents.loadingCredits")} className="mt-1" />
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              {canAuthor
                ? t("documents.authorHint", { balance })
                : t("documents.memberHint")}{" "}
              {canAuthor ? (
                <Link href="/account" className="font-medium text-accent hover:underline">
                  {t("documents.buyCredits")}
                </Link>
              ) : null}
            </p>
          )}
        </div>
        {canAuthor ? (
          <div>
            <input
              ref={inputRef}
              type="file"
              accept="application/pdf,.pdf,.txt,.md"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) upload.mutate(file);
                event.target.value = "";
              }}
            />
            <Button type="button" onClick={() => inputRef.current?.click()} loading={upload.isPending}>
              {upload.isPending ? t("documents.uploading") : t("documents.upload")}
            </Button>
          </div>
        ) : null}
      </div>

      {uploadProgress ? (
        <Card>
          <ProgressBar
            kind="percent"
            max={100}
            value={uploadProgress.phase === "uploading" ? uploadProgress.percent : 0}
            showValue={uploadProgress.phase === "uploading"}
            label={
              uploadProgress.phase === "uploading"
                ? t("documents.uploadProgress", { name: uploadProgress.filename })
                : t("documents.processingFile", { name: uploadProgress.filename })
            }
          />
        </Card>
      ) : null}

      {examDoc ? (
        <Card>
          <CardTitle>{t("documents.newExam")}</CardTitle>
          <CardDescription>
            {t("documents.newExamBody", {
              title: examDoc.title || examDoc.filename,
              cost: CREDIT_PER_QUESTION,
            })}
          </CardDescription>
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="question-count">{t("documents.questionCount")}</Label>
              <div className="flex flex-wrap gap-2">
                {QUESTION_PRESETS.map((count) => (
                  <Button
                    key={count}
                    type="button"
                    size="sm"
                    variant={questionCount === count ? "primary" : "outline"}
                    onClick={() => setQuestionCount(count)}
                  >
                    {count}
                  </Button>
                ))}
              </div>
              <Input
                id="question-count"
                type="number"
                min={MIN_QUESTIONS}
                max={MAX_QUESTIONS}
                value={questionCount}
                onChange={(event) => {
                  const next = Number(event.target.value);
                  if (!Number.isFinite(next)) return;
                  setQuestionCount(Math.min(MAX_QUESTIONS, Math.max(MIN_QUESTIONS, Math.round(next))));
                }}
                className="mt-2 max-w-[8rem]"
              />
              <p className="text-xs text-muted-foreground">
                {t("documents.costRange", {
                  min: MIN_QUESTIONS,
                  max: MAX_QUESTIONS,
                  cost: examCountValid ? examCost : "—",
                  balance,
                })}
                {` ${examCost === 1 ? t("common.credit") : t("common.credits")}`}
              </p>
              {examCountValid && !canAffordExam ? (
                <p className="text-sm text-destructive">
                  {t("documents.notEnough", { count: questionCount })}{" "}
                  <Link href="/account" className="font-medium underline">
                    {t("documents.buyCredits")}
                  </Link>
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                disabled={!canAffordExam || generateExam.isPending}
                loading={generateExam.isPending}
                onClick={() => {
                  setActionError(null);
                  generateExam.mutate({ documentId: examDoc.id, questionCount });
                }}
              >
                {generateExam.isPending
                  ? t("documents.generating")
                  : t("documents.generateCost", { cost: examCountValid ? examCost : "—" })}
              </Button>
              <Button type="button" variant="outline" onClick={() => setExamDoc(null)} disabled={generateExam.isPending}>
                {t("common.cancel")}
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {documents.isError ? (
        <ErrorState
          title={t("documents.loadError")}
          error={documents.error}
          onRetry={() => void documents.refetch()}
        />
      ) : documents.isLoading ? (
        <ListLoader label={t("documents.loadingList")} />
      ) : documents.data?.length ? (
        <ul className={surfaceListClass}>
          {documents.data.map((doc) => (
            <li key={doc.id} className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex min-w-0 items-center gap-4">
                <DocumentCover
                  documentId={doc.id}
                  hasCover={doc.has_cover}
                  kind={doc.document_kind}
                  title={doc.title || doc.filename}
                />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{doc.title || doc.filename}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {doc.title !== doc.filename ? `${doc.filename} · ` : ""}
                    {doc.page_count ? `${t("documents.pages", { count: doc.page_count })} · ` : ""}
                    {formatDateTime(doc.created_at, locale)}
                    {doc.error_message ? ` · ${doc.error_message}` : ""}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {doc.status === "uploaded" || doc.status === "processing" ? (
                  <ProgressBar
                    compact
                    className="w-40"
                    value={0}
                    max={1}
                    showValue={false}
                    label={doc.status === "uploaded" ? t("status.queued") : t("status.processing")}
                  />
                ) : (
                  <Badge
                    className={
                      doc.status === "ready"
                        ? "border-accent/30 bg-accent/10 text-accent"
                        : doc.status === "failed"
                          ? "border-destructive/30 bg-destructive/10 text-destructive"
                          : undefined
                    }
                  >
                    {t(`status.${doc.status}`)}
                  </Badge>
                )}
                {doc.status === "ready" && canAuthor ? (
                  <>
                    <Button
                      size="sm"
                      disabled={busyId === doc.id}
                      onClick={() => {
                        setActionError(null);
                        setQuestionCount(10);
                        setExamDoc(doc);
                      }}
                    >
                      <BookOpen className="h-3.5 w-3.5" />
                      {t("documents.exam")}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-accent/40 text-accent hover:bg-accent/10 hover:text-accent"
                      disabled={busyId === doc.id || !canAffordCards}
                      loading={generateCards.isPending && generateCards.variables === doc.id}
                      onClick={() => {
                        setActionError(null);
                        generateCards.mutate(doc.id);
                      }}
                    >
                      <Layers className="h-3.5 w-3.5" />
                      {t("documents.flashcardsCost")}
                    </Button>
                  </>
                ) : null}
                {canAuthor ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busyId === doc.id}
                    loading={remove.isPending && remove.variables === doc.id}
                    onClick={() => {
                      const title = doc.title || doc.filename;
                      if (!window.confirm(t("documents.deleteConfirm", { title }))) return;
                      setActionError(null);
                      remove.mutate(doc.id);
                    }}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    {t("documents.delete")}
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : uploadProgress ? null : (
        <EmptyState
          title={t("documents.emptyTitle")}
          description={canAuthor ? t("documents.emptyAuthor") : t("documents.emptyMember")}
        />
      )}
      {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
    </div>
  );
}
