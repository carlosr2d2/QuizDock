"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { DocumentCover } from "@/components/document-cover";
import { AttemptHistoryCard, AttemptRow } from "@/components/attempt-row";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { PageLoader, Loader, ProgressBar } from "@/components/ui/loader";
import { ErrorState } from "@/components/ui/error-state";
import { apiFetch } from "@/lib/api";
import { cn, formatDateTime, formatScore } from "@/lib/utils";
import type {
  Attempt,
  AttemptSummary,
  ExamAssignment,
  ExamDetail,
  QuestionKind,
  QuestionPublic,
  QuestionResult,
  TeamSnapshot,
} from "@/types/api";

export default function ExamPlayerPage() {
  return (
    <Suspense fallback={<PageLoader label="Cargando evaluación…" />}>
      <ExamPlayer />
    </Suspense>
  );
}

function ExamPlayer() {
  const params = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const examId = params.id;
  const requestedAttemptId = searchParams.get("attempt");
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, number | number[]>>({});
  const [result, setResult] = useState<Attempt | null>(null);
  const [taking, setTaking] = useState(false);
  const [viewedAttemptId, setViewedAttemptId] = useState<string | null>(null);

  const exam = useQuery({
    queryKey: ["exam", examId],
    queryFn: () => apiFetch<ExamDetail>(`/api/v1/exams/${examId}`),
    refetchOnMount: "always",
    refetchInterval: (query) => (query.state.data?.status === "generating" ? 1000 : false),
  });

  const submit = useMutation({
    mutationFn: () =>
      apiFetch<Attempt>(`/api/v1/exams/${examId}/attempts`, {
        method: "POST",
        body: { answers },
      }),
    onSuccess: async (attempt) => {
      setResult(attempt);
      setTaking(false);
      setViewedAttemptId(attempt.id);
      await queryClient.invalidateQueries({ queryKey: ["exam", examId] });
      await queryClient.invalidateQueries({ queryKey: ["exams"] });
      await queryClient.invalidateQueries({ queryKey: ["progress"] });
    },
  });

  const openAttempt = useMutation({
    mutationFn: (attemptId: string) =>
      apiFetch<Attempt>(`/api/v1/exams/${examId}/attempts/${attemptId}`),
    onSuccess: (attempt) => {
      setResult(attempt);
      setTaking(false);
    },
  });

  const latestAttemptId = exam.data?.attempts?.[0]?.id;
  const targetAttemptId = taking
    ? null
    : (viewedAttemptId ?? requestedAttemptId ?? latestAttemptId ?? null);
  const history = useMemo(() => {
    const items = exam.data?.attempts ?? [];
    if (result && !items.some((item) => item.id === result.id)) {
      return [
        {
          id: result.id,
          exam_id: result.exam_id,
          score: result.score,
          completed_at: result.completed_at,
        },
        ...items,
      ];
    }
    return items;
  }, [exam.data?.attempts, result]);

  useEffect(() => {
    if (!targetAttemptId || result?.id === targetAttemptId) return;
    openAttempt.mutate(targetAttemptId);
    // mutate is stable; we only reopen when the target attempt changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetAttemptId, result?.id]);

  function redo() {
    setResult(null);
    setAnswers({});
    setViewedAttemptId(null);
    setTaking(true);
  }

  function viewAttempt(item: AttemptSummary) {
    setViewedAttemptId(item.id);
    openAttempt.mutate(item.id);
  }

  if (exam.isLoading) {
    return <PageLoader label="Cargando evaluación…" />;
  }
  if (exam.error || !exam.data) {
    return (
      <ErrorState
        title="No se pudo abrir la evaluación"
        error={exam.error ?? new Error("No encontrado")}
        onRetry={() => void exam.refetch()}
      />
    );
  }

  const data = exam.data;

  const heading = (
    <div className="flex items-start gap-4">
      <DocumentCover
        documentId={data.document_id}
        hasCover={data.has_cover}
        kind={data.document_kind}
        title={data.document_title ?? data.title}
        className="h-24 w-[4.5rem]"
      />
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>
        {data.document_title && data.document_title !== data.title ? (
          <p className="mt-1 text-sm text-muted-foreground">{data.document_title}</p>
        ) : null}
        {data.attempt_count ? (
          <p className="mt-1 text-sm text-muted-foreground">
            Última {formatScore(data.last_score)} · {data.attempt_count}{" "}
            {data.attempt_count === 1 ? "intento" : "intentos"}
          </p>
        ) : null}
        {data.assigned_to_me && data.assignment_status === "pending" ? (
          <p className="mt-1 text-sm text-accent">Asignado por tu empresa · pendiente</p>
        ) : null}
      </div>
    </div>
  );

  const assignPanel =
    data.can_assign && data.status === "ready" ? (
      <AssignPanel
        examId={examId}
        exam={data}
        activeAttemptId={result?.id ?? viewedAttemptId}
        onViewAttempt={(attemptId) => {
          setTaking(false);
          setViewedAttemptId(attemptId);
          openAttempt.mutate(attemptId);
        }}
      />
    ) : null;

  if (data.status === "generating") {
    const total = data.question_count || 1;
    const current = data.generated_count ?? 0;
    const label =
      current > 0
        ? `Creando pregunta ${current} de ${total}`
        : "Preparando el documento y los fragmentos…";
    return (
      <div className="space-y-6">
        <Badge>generando</Badge>
        {heading}
        <div className="max-w-lg rounded-xl border border-border bg-card p-5">
          <ProgressBar value={current} max={total} label={label} />
          <p className="mt-3 text-xs text-muted-foreground">
            Esta vista se actualiza sola. Verdadero/falso y opción múltiple se generan en paralelo.
          </p>
        </div>
      </div>
    );
  }

  if (data.status === "failed") {
    return (
      <div className="space-y-3">
        <Badge>error</Badge>
        {heading}
        <p className="text-sm text-destructive">
          {data.error_message ?? "La generación falló. Los créditos se reembolsaron."}
        </p>
        <Link href="/documents" className="text-sm underline-offset-4 hover:underline">
          Volver a documentos
        </Link>
      </div>
    );
  }

  if (!taking && targetAttemptId && !result) {
    return (
      <div className="space-y-3">
        {heading}
        {assignPanel}
        <PageLoader label="Cargando intento…" />
        {openAttempt.error ? (
          <p className="text-sm text-destructive">{openAttempt.error.message}</p>
        ) : null}
      </div>
    );
  }

  if (result && !taking) {
    return (
      <div className="space-y-8">
        {heading}
        {assignPanel}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-sm text-muted-foreground">
              {result.is_own ? "Tu resultado" : `Respuestas de ${result.full_name || result.email}`}
            </p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight">{formatScore(result.score)}</h2>
            <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(result.completed_at)}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {result.is_own ? (
              <Button type="button" onClick={redo}>
                Rehacer
              </Button>
            ) : null}
            <Link href="/exams">
              <Button variant="outline">Volver a exámenes</Button>
            </Link>
          </div>
        </div>
        {result.is_own ? (
          <AttemptHistory
            attempts={history}
            activeId={result.id}
            onSelect={viewAttempt}
          />
        ) : null}
        <ol className="space-y-4">
          {result.results.map((item, index) => (
            <li key={item.question_id} className="rounded-xl border border-border bg-card p-5">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="text-sm font-medium">
                  {index + 1}. {item.prompt}
                </p>
                <Badge>{questionKindLabel(item.kind)}</Badge>
              </div>
              <p className={cn("mt-2 text-sm", item.is_correct ? "text-accent" : "text-destructive")}>
                {item.is_correct ? "Correcto" : "Incorrecto"}
              </p>
              <AttemptAnswer item={item} />
              {item.explanation ? (
                <p className="mt-2 text-sm text-muted-foreground">{item.explanation}</p>
              ) : null}
            </li>
          ))}
        </ol>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        {heading}
        {assignPanel}
      </div>
    <form
      className="space-y-8"
      onSubmit={(event) => {
        event.preventDefault();
        submit.mutate();
      }}
    >
      <p className="text-sm text-muted-foreground">
          {data.questions.length} preguntas · verdadero/falso y opción múltiple · respuestas al enviar
          {history.length ? " · rehacer no consume créditos extra" : ""}
        </p>
      <AttemptHistory attempts={history} onSelect={viewAttempt} />
      {openAttempt.error ? (
        <p className="text-sm text-destructive">{openAttempt.error.message}</p>
      ) : null}

      <ol className="space-y-6">
        {data.questions.map((question, index) => (
          <li key={question.id} className="rounded-xl border border-border bg-card p-5">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <p className="text-sm font-medium">
                {index + 1}. {question.prompt}
              </p>
              <Badge>{questionKindLabel(question.kind)}</Badge>
            </div>
            {question.kind === "multiple_choice" ? (
              <p className="mt-2 text-xs text-muted-foreground">Selecciona todas las correctas.</p>
            ) : null}
            <QuestionOptions
              question={question}
              value={answers[question.id]}
              onChange={(value) => setAnswers((current) => ({ ...current, [question.id]: value }))}
            />
          </li>
        ))}
      </ol>

      {submit.error ? <p className="text-sm text-destructive">{submit.error.message}</p> : null}
      <Button type="submit" loading={submit.isPending} disabled={data.questions.length === 0}>
        {submit.isPending ? "Enviando…" : data.attempt_count ? "Enviar de nuevo" : "Enviar respuestas"}
      </Button>
    </form>
    </div>
  );
}

function questionKindLabel(kind?: QuestionKind | string) {
  switch (kind) {
    case "true_false":
      return "Falso / Verdadero";
    case "multiple_choice":
      return "Varias correctas";
    default:
      return "Opción múltiple";
  }
}

function selectedIndices(value: number | number[] | undefined): number[] {
  if (Array.isArray(value)) return value;
  if (typeof value === "number") return [value];
  return [];
}

function formatChoices(options: string[], indices: number[]) {
  if (!indices.length) return "Sin respuesta";
  return indices
    .map((index) => options[index])
    .filter(Boolean)
    .join(" · ");
}

function QuestionOptions({
  question,
  value,
  onChange,
}: {
  question: QuestionPublic;
  value: number | number[] | undefined;
  onChange: (value: number | number[]) => void;
}) {
  const multi = question.kind === "multiple_choice";
  const selected = selectedIndices(value);

  function toggle(optionIndex: number) {
    const next = selected.includes(optionIndex)
      ? selected.filter((index) => index !== optionIndex)
      : [...selected, optionIndex].sort((left, right) => left - right);
    onChange(next);
  }

  return (
    <fieldset className="mt-4 space-y-2">
      {question.options.map((option, optionIndex) => (
        <label
          key={`${question.id}-${optionIndex}`}
          className="flex cursor-pointer items-start gap-3 rounded-md border border-transparent px-2 py-2 hover:bg-muted"
        >
          <input
            type={multi ? "checkbox" : "radio"}
            className="mt-1"
            name={question.id}
            checked={multi ? selected.includes(optionIndex) : value === optionIndex}
            onChange={() => (multi ? toggle(optionIndex) : onChange(optionIndex))}
            required={!multi}
          />
          <span className="text-sm">{option}</span>
        </label>
      ))}
    </fieldset>
  );
}

function AttemptAnswer({ item }: { item: QuestionResult }) {
  const selected = item.selected_indices?.length
    ? item.selected_indices
    : item.selected_index != null
      ? [item.selected_index]
      : [];
  const correct = item.correct_indices?.length ? item.correct_indices : [item.correct_index];
  if (item.is_correct) {
    return (
      <p className="mt-2 text-sm text-muted-foreground">Tu respuesta: {formatChoices(item.options, selected)}</p>
    );
  }
  return (
    <div className="mt-2 space-y-1 text-sm text-muted-foreground">
      <p>Tu respuesta: {formatChoices(item.options, selected)}</p>
      <p>Correcta: {formatChoices(item.options, correct)}</p>
    </div>
  );
}

function AttemptHistory({
  attempts,
  activeId,
  onSelect,
}: {
  attempts: AttemptSummary[];
  activeId?: string;
  onSelect: (item: AttemptSummary) => void;
}) {
  if (!attempts.length) return null;
  return (
    <AttemptHistoryCard description="Abre un intento para ver tus respuestas y la corrección.">
      {attempts.map((item, index) => (
        <li key={item.id}>
          <AttemptRow
            title={`Intento ${attempts.length - index}`}
            subtitle={formatDateTime(item.completed_at)}
            score={item.score}
            active={item.id === activeId}
            onClick={() => onSelect(item)}
          />
        </li>
      ))}
    </AttemptHistoryCard>
  );
}

function AssignPanel({
  examId,
  exam,
  activeAttemptId,
  onViewAttempt,
}: {
  examId: string;
  exam: ExamDetail;
  activeAttemptId?: string | null;
  onViewAttempt: (attemptId: string) => void;
}) {
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const team = useQuery({
    queryKey: ["team"],
    queryFn: () => apiFetch<TeamSnapshot>("/api/v1/organizations/current/team"),
  });
  const assign = useMutation({
    mutationFn: (body: { user_ids?: string[]; all_members?: boolean }) =>
      apiFetch<ExamAssignment[]>(`/api/v1/exams/${examId}/assignments`, { method: "POST", body }),
    onSuccess: async () => {
      setSelected([]);
      await queryClient.invalidateQueries({ queryKey: ["exam", examId] });
      await queryClient.invalidateQueries({ queryKey: ["exams"] });
    },
  });
  const unassign = useMutation({
    mutationFn: (userId: string) =>
      apiFetch<void>(`/api/v1/exams/${examId}/assignments/${userId}`, { method: "DELETE" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["exam", examId] });
      await queryClient.invalidateQueries({ queryKey: ["exams"] });
    },
  });

  const assignedIds = new Set((exam.assignments ?? []).map((item) => item.user_id));
  const available = (team.data?.members ?? []).filter((member) => !assignedIds.has(member.user_id));

  function toggle(userId: string) {
    setSelected((current) =>
      current.includes(userId) ? current.filter((id) => id !== userId) : [...current, userId],
    );
  }

  return (
    <Card className="mt-6">
      <CardTitle>Asignar a empleados</CardTitle>
      <CardDescription>
        El miembro verá este examen como pendiente en su workspace de empresa. Si ya lo hizo, abre la fila
        para ver sus respuestas.
      </CardDescription>
      {exam.assignments?.length ? (
        <ul className="mt-4 space-y-1">
          {exam.assignments.map((item) => {
            const canOpen =
              item.status.toLowerCase() === "completed" && Boolean(item.last_attempt_id);
            return (
              <li key={item.id}>
                {canOpen ? (
                  <AttemptRow
                    title={item.full_name}
                    subtitle={item.email}
                    score={item.last_score ?? 0}
                    active={activeAttemptId === item.last_attempt_id}
                    actionLabel="Ver respuestas"
                    onClick={() => onViewAttempt(item.last_attempt_id!)}
                  />
                ) : (
                  <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.full_name}</p>
                      <p className="text-xs text-muted-foreground">{item.email}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge>pendiente</Badge>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => unassign.mutate(item.user_id)}
                        loading={unassign.isPending && unassign.variables === item.user_id}
                      >
                        Quitar
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">Nadie lo tiene asignado todavía.</p>
      )}
      {team.isLoading ? (
        <Loader label="Cargando miembros…" className="mt-4" />
      ) : available.length ? (
        <div className="mt-4 space-y-3">
          <ul className="space-y-2">
            {available.map((member) => (
              <li key={member.user_id}>
                <label className="flex cursor-pointer items-center gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.includes(member.user_id)}
                    onChange={() => toggle(member.user_id)}
                  />
                  <span>
                    {member.full_name}{" "}
                    <span className="text-muted-foreground">· {member.email}</span>
                  </span>
                </label>
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              onClick={() => assign.mutate({ user_ids: selected })}
              loading={assign.isPending}
              disabled={!selected.length}
            >
              {assign.isPending ? "Asignando…" : "Asignar seleccionados"}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => assign.mutate({ all_members: true })}
              loading={assign.isPending}
            >
              {assign.isPending ? "Asignando…" : "Asignar a todos"}
            </Button>
          </div>
        </div>
      ) : team.data && !available.length ? (
        <p className="mt-3 text-sm text-muted-foreground">Todos los miembros ya están asignados.</p>
      ) : null}
      {assign.error ? <p className="mt-3 text-sm text-destructive">{assign.error.message}</p> : null}
    </Card>
  );
}
