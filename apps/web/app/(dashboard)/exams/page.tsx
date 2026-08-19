"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { AttemptRow } from "@/components/attempt-row";
import { DocumentCover } from "@/components/document-cover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle, surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ListLoader, Loader, ProgressBar } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { canCreateContent } from "@/lib/permissions";
import { formatDateTime, formatScore } from "@/lib/utils";
import type { Exam, Progress, User } from "@/types/api";

export default function ExamsPage() {
  const exams = useQuery({
    queryKey: ["exams"],
    queryFn: () => apiFetch<Exam[]>("/api/v1/exams"),
    refetchOnMount: "always",
    refetchInterval: (query) => {
      const items = query.state.data ?? [];
      return items.some((exam) => exam.status === "generating") ? 1000 : false;
    },
  });
  const progress = useQuery({
    queryKey: ["progress"],
    queryFn: () => apiFetch<Progress>("/api/v1/progress"),
    refetchOnMount: "always",
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
  });
  const canAuthor = canCreateContent(me.data);

  const recent = progress.data?.recent ?? [];
  const items = exams.data ?? [];
  const pendingAssigned = items.filter(
    (exam) => exam.assigned_to_me && exam.assignment_status === "pending" && exam.status === "ready",
  );
  const pendingIds = new Set(pendingAssigned.map((exam) => exam.id));
  const catalog = items.filter((exam) => !pendingIds.has(exam.id));

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Exámenes</h1>
        {exams.isLoading ? (
          <Loader label="Cargando evaluaciones…" className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {exams.data?.some((exam) => exam.can_assign)
              ? "Asigna evaluaciones del workspace a los miembros del equipo."
              : exams.data?.some((exam) => exam.assigned_to_me)
                ? "Lo que tu empresa te pidió completar, y tu historial."
                : canAuthor
                  ? "Evaluaciones generadas a partir de documentos. El worker descuenta créditos y no bloquea la API."
                  : "Los exámenes los crea un administrador. Aquí ves los que te asignaron y tu historial."}
          </p>
        )}
      </div>

      {exams.isError ? (
        <ErrorState
          title="No se pudieron cargar los exámenes"
          error={exams.error}
          onRetry={() => void exams.refetch()}
        />
      ) : exams.isLoading ? (
        <ListLoader label="Cargando exámenes…" />
      ) : pendingAssigned.length ? (
        <div className="space-y-3">
          <h2 className="text-sm font-medium text-muted-foreground">Pendientes de la empresa</h2>
          <ul className={surfaceListClass}>
            {pendingAssigned.map((exam) => (
              <ExamRow key={exam.id} exam={exam} pending />
            ))}
          </ul>
        </div>
      ) : null}

      {catalog.length ? (
        <ul className={surfaceListClass}>
          {catalog.map((exam) => (
            <ExamRow key={exam.id} exam={exam} />
          ))}
        </ul>
      ) : !exams.isLoading && !exams.isError && !pendingAssigned.length ? (
        <EmptyState
          title="Sin evaluaciones todavía"
          description={
            canAuthor
              ? "Cuando un documento esté listo, genera un cuestionario desde la lista de documentos."
              : "Cuando un administrador genere y te asigne un examen, aparecerá aquí."
          }
        >
          {canAuthor ? (
            <Link href="/documents">
              <Button variant="outline">Ir a documentos</Button>
            </Link>
          ) : null}
        </EmptyState>
      ) : null}

      {progress.isLoading ? <Loader label="Cargando historial…" className="py-4" /> : recent.length ? (
        <Card>
          <CardTitle>Historial de intentos</CardTitle>
          <CardDescription>Abre un intento para ver tus respuestas y la corrección.</CardDescription>
          <ul className="mt-4 space-y-1">
            {recent.map((item) => (
              <li key={item.id}>
                <AttemptRow
                  title={item.exam_title}
                  subtitle={formatDateTime(item.completed_at)}
                  score={item.score}
                  href={`/exams/${item.exam_id}?attempt=${item.id}`}
                />
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
    </div>
  );
}

function ExamRow({ exam, pending = false }: { exam: Exam; pending?: boolean }) {
  const assignmentLabel =
    exam.can_assign && exam.assignment_count
      ? `${exam.assignment_completed_count}/${exam.assignment_count} hechos`
      : exam.assigned_to_me && exam.assignment_status === "completed"
        ? "hecho"
        : exam.attempt_count
          ? `${exam.attempt_count} ${exam.attempt_count === 1 ? "intento" : "intentos"}`
          : examStatusLabel(exam.status);

  return (
    <li className="flex items-center justify-between gap-4 px-5 py-4">
      <div className="flex min-w-0 items-center gap-4">
        <DocumentCover
          documentId={exam.document_id}
          hasCover={exam.has_cover}
          kind={exam.document_kind}
          title={exam.document_title ?? exam.title}
        />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{exam.title}</p>
          <p className="text-xs text-muted-foreground">
            {exam.kind} · {exam.question_count} preguntas
            {exam.error_message ? ` · ${exam.error_message}` : ""}
          </p>
          {exam.status === "ready" ? (
            <p className="mt-1 text-xs">
              {exam.can_assign && exam.assignment_count ? (
                <span className="text-accent">
                  {exam.assignment_completed_count} de {exam.assignment_count}{" "}
                  {exam.assignment_count === 1 ? "asignado" : "asignados"} completaron
                </span>
              ) : exam.attempt_count ? (
                <span className="text-accent">
                  Última {formatScore(exam.last_score)} · {exam.attempt_count}{" "}
                  {exam.attempt_count === 1 ? "intento" : "intentos"}
                </span>
              ) : pending ? (
                <span className="text-accent">Asignado · pendiente</span>
              ) : (
                <span className="text-muted-foreground">Aún no lo has hecho</span>
              )}
            </p>
          ) : null}
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Badge
          className={
            pending || (exam.status === "ready" && (exam.attempt_count || exam.assignment_count))
              ? "border-accent/30 bg-accent/10 text-accent"
              : undefined
          }
        >
          {pending ? "pendiente" : assignmentLabel}
        </Badge>
        {exam.status === "ready" ? (
          <>
            {exam.can_assign ? (
              <Link href={`/exams/${exam.id}`}>
                <Button size="sm" variant="outline">
                  Asignar
                </Button>
              </Link>
            ) : null}
            <Link href={`/exams/${exam.id}`}>
              <Button size="sm">
                {pending ? "Hacer" : exam.attempt_count ? "Ver historial" : exam.can_assign ? "Ver" : "Hacer"}
              </Button>
            </Link>
          </>
        ) : exam.status === "generating" ? (
          <ProgressBar
            compact
            className="w-36"
            value={exam.generated_count ?? 0}
            max={exam.question_count || 1}
            label="Generando…"
          />
        ) : null}
      </div>
    </li>
  );
}

function examStatusLabel(status: Exam["status"]) {
  switch (status) {
    case "generating":
      return "generando";
    case "ready":
      return "listo";
    case "failed":
      return "error";
    case "assigned":
      return "asignado";
    case "archived":
      return "archivo";
    default:
      return status;
  }
}
