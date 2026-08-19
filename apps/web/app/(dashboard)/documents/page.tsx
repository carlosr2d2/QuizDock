"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { BookOpen, Layers } from "lucide-react";
import { useRef, useState } from "react";

import { DocumentCover } from "@/components/document-cover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle, surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ListLoader, Loader, Spinner } from "@/components/ui/loader";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import { canCreateContent } from "@/lib/permissions";
import { cn } from "@/lib/utils";
import type { CreditBalance, Document, Exam, GenerationJob, User } from "@/types/api";

const MIN_QUESTIONS = 1;
const MAX_QUESTIONS = 50;
const CREDIT_PER_QUESTION = 1;
const QUESTION_PRESETS = [5, 10, 15, 20, 30];

export default function DocumentsPage() {
  const inputRef = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const router = useRouter();
  const [actionError, setActionError] = useState<string | null>(null);
  const [examDoc, setExamDoc] = useState<Document | null>(null);
  const [questionCount, setQuestionCount] = useState(10);

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
      const body = new FormData();
      body.append("file", file);
      body.append("language", "auto");
      return apiFetch<Document>("/api/v1/documents", { method: "POST", body });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });

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
        body: { document_id: documentId, card_count: 12 },
      }),
    onSuccess: (job) => {
      queryClient.invalidateQueries({ queryKey: ["credits"] });
      router.push(`/flashcards?job=${job.id}`);
    },
    onError: (error: Error) => setActionError(error.message),
  });

  const busyId = generateExam.variables?.documentId ?? generateCards.variables ?? null;
  const balance = credits.data?.balance ?? 0;
  const examCost = questionCount * CREDIT_PER_QUESTION;
  const examCountValid = questionCount >= MIN_QUESTIONS && questionCount <= MAX_QUESTIONS;
  const canAffordExam = examCountValid && examCost <= balance;

  return (
    <div className="space-y-8">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documentos</h1>
          {credits.isLoading ? (
            <Loader label="Consultando créditos…" className="mt-1" />
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">
              {canAuthor
                ? `Ingesta asíncrona y generación de evaluaciones. ${balance} créditos disponibles · 1 crédito por pregunta.`
                : "Consulta los documentos del workspace. Solo un administrador puede subir archivos o generar exámenes."}
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
              {upload.isPending ? "Subiendo…" : "Subir documento"}
            </Button>
          </div>
        ) : null}
      </div>

      {examDoc ? (
        <Card>
          <CardTitle>Nuevo examen</CardTitle>
          <CardDescription>
            {examDoc.title || examDoc.filename}. Elige cuántas preguntas generar. Cada una cuesta{" "}
            {CREDIT_PER_QUESTION} crédito. El examen mezcla verdadero/falso y opción múltiple (una o
            varias correctas).
          </CardDescription>
          <div className="mt-4 space-y-4">
            <div className="space-y-2">
              <Label htmlFor="question-count">Número de preguntas</Label>
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
                Entre {MIN_QUESTIONS} y {MAX_QUESTIONS}. Coste:{" "}
                <span className={cn(!canAffordExam && "text-destructive")}>
                  {examCountValid ? examCost : "—"} {examCost === 1 ? "crédito" : "créditos"}
                </span>
                {` · saldo ${balance}`}
              </p>
              {examCountValid && !canAffordExam ? (
                <p className="text-sm text-destructive">
                  No hay créditos suficientes para {questionCount} preguntas.
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
                  ? "Generando…"
                  : `Generar examen · ${examCountValid ? examCost : "—"} cr.`}
              </Button>
              <Button type="button" variant="outline" onClick={() => setExamDoc(null)} disabled={generateExam.isPending}>
                Cancelar
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {documents.isError ? (
        <ErrorState
          title="No se pudieron cargar los documentos"
          error={documents.error}
          onRetry={() => void documents.refetch()}
        />
      ) : documents.isLoading ? (
        <ListLoader label="Cargando documentos…" />
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
                    {doc.page_count ? `${doc.page_count} páginas · ` : ""}
                    {new Date(doc.created_at).toLocaleString()}
                    {doc.error_message ? ` · ${doc.error_message}` : ""}
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  className={
                    doc.status === "ready"
                      ? "border-accent/30 bg-accent/10 text-accent"
                      : doc.status === "failed"
                        ? "border-destructive/30 bg-destructive/10 text-destructive"
                        : "gap-1.5"
                  }
                >
                  {doc.status === "uploaded" || doc.status === "processing" ? (
                    <Spinner className="h-3 w-3" />
                  ) : null}
                  {statusLabel(doc.status)}
                </Badge>
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
                      Examen
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      className="border-accent/40 text-accent hover:bg-accent/10 hover:text-accent"
                      disabled={busyId === doc.id}
                      loading={generateCards.isPending && generateCards.variables === doc.id}
                      onClick={() => {
                        setActionError(null);
                        generateCards.mutate(doc.id);
                      }}
                    >
                      <Layers className="h-3.5 w-3.5" />
                      Flashcards · 12 cr.
                    </Button>
                  </>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          title="Aún no hay documentos"
          description={
            canAuthor
              ? "Sube un PDF, Markdown o texto. Cuando el estado sea listo, genera un examen o flashcards."
              : "Un administrador del equipo debe subir los documentos de este workspace."
          }
        />
      )}
      {upload.error ? <p className="text-sm text-destructive">{upload.error.message}</p> : null}
      {actionError ? <p className="text-sm text-destructive">{actionError}</p> : null}
    </div>
  );
}

function statusLabel(status: Document["status"]) {
  switch (status) {
    case "uploaded":
      return "en cola";
    case "processing":
      return "procesando";
    case "ready":
      return "listo";
    case "failed":
      return "error";
  }
}
