"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { AttemptRow } from "@/components/attempt-row";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Loader, Skeleton } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { canCreateContent } from "@/lib/permissions";
import { getOrgId, getToken, setSession } from "@/lib/session";
import { formatDate, formatDateTime, formatScore } from "@/lib/utils";
import type { CreditBalance, Document, Exam, InvitationAccept, MyInvitation, Progress, User } from "@/types/api";

export default function OverviewPage() {
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
  });
  const documents = useQuery({
    queryKey: ["documents"],
    queryFn: () => apiFetch<Document[]>("/api/v1/documents"),
  });
  const exams = useQuery({
    queryKey: ["exams"],
    queryFn: () => apiFetch<Exam[]>("/api/v1/exams"),
  });
  const credits = useQuery({
    queryKey: ["credits"],
    queryFn: () => apiFetch<CreditBalance>("/api/v1/billing/credits"),
  });
  const progress = useQuery({
    queryKey: ["progress"],
    queryFn: () => apiFetch<Progress>("/api/v1/progress"),
    refetchOnMount: "always",
  });
  const invites = useQuery({
    queryKey: ["my-invitations"],
    queryFn: () => apiFetch<MyInvitation[]>("/api/v1/invitations"),
  });
  const acceptInvite = useMutation({
    mutationFn: (token: string) =>
      apiFetch<InvitationAccept>(`/api/v1/invitations/${token}/accept`, { method: "POST" }),
    onSuccess: async (result) => {
      const access = getToken();
      const user = await apiFetch<User>("/api/v1/auth/me");
      if (!access) return;
      await setSession(access, result.organization.id, JSON.stringify(user));
      window.location.assign("/overview");
    },
  });

  const currentOrgId = getOrgId();
  const workspace =
    me.data?.memberships.find((m) => m.organization_id === currentOrgId)?.organization ??
    me.data?.memberships.find((m) => m.organization_id === me.data?.personal_organization_id)
      ?.organization;
  const snapshot = progress.data;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Resumen</h1>
        {me.isLoading || credits.isLoading ? (
          <Loader label="Cargando workspace…" className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {workspace?.name ?? "Tu workspace"} · plan {credits.data?.plan ?? "—"}
          </p>
        )}
      </div>

      {invites.isLoading ? <Loader label="Buscando invitaciones…" /> : null}
      {invites.data?.length ? (
        <Card>
          <CardTitle>Te invitaron a un equipo</CardTitle>
          <CardDescription>Acepta para entrar al workspace compartido. Tu espacio personal no se mezcla.</CardDescription>
          <ul className="mt-4 space-y-2">
            {invites.data.map((item) => (
              <li key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{item.organization_name}</p>
                  <p className="text-xs text-muted-foreground">caduca {formatDate(item.expires_at)}</p>
                </div>
                <Button
                  size="sm"
                  loading={acceptInvite.isPending && acceptInvite.variables === item.token}
                  onClick={() => acceptInvite.mutate(item.token)}
                >
                  Unirme
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {exams.isError || documents.isError || progress.isError || credits.isError ? (
        <ErrorState
          title="No se pudo cargar el resumen"
          error={exams.error ?? documents.error ?? progress.error ?? credits.error}
          onRetry={() => {
            void exams.refetch();
            void documents.refetch();
            void progress.refetch();
            void credits.refetch();
          }}
        />
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat title="Créditos" value={credits.data?.balance ?? "—"} href="/documents" loading={credits.isLoading} />
        <Stat title="Documentos" value={documents.data?.length ?? "—"} href="/documents" loading={documents.isLoading} />
        <Stat title="Exámenes" value={exams.data?.length ?? "—"} href="/exams" loading={exams.isLoading} />
        <Stat title="Flashcards" value={snapshot?.flashcard_count ?? "—"} href="/flashcards" loading={progress.isLoading} />
      </div>

      <div>
        <h2 className="text-sm font-medium text-muted-foreground">Repaso</h2>
        {progress.isLoading ? (
          <Loader label="Cargando repaso…" className="mt-1" />
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">
            {snapshot?.flashcard_count
              ? snapshot.flashcard_due
                ? `${snapshot.flashcard_due} ${snapshot.flashcard_due === 1 ? "tarjeta pendiente" : "tarjetas pendientes"} de ${snapshot.flashcard_count}`
                : `Al día · ${snapshot.flashcard_count} ${snapshot.flashcard_count === 1 ? "tarjeta" : "tarjetas"}`
              : "Cuando generes flashcards, aquí verás pendientes y último repaso."}
          </p>
        )}
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat title="Pendientes" value={snapshot?.flashcard_due ?? 0} href="/flashcards" loading={progress.isLoading} />
          <Stat title="Repasadas" value={snapshot?.flashcard_reviewed ?? 0} href="/flashcards" loading={progress.isLoading} />
          <Stat title="En el mazo" value={snapshot?.flashcard_count ?? 0} href="/flashcards" loading={progress.isLoading} />
          <Stat
            title="Último repaso"
            value={
              snapshot?.flashcard_last_reviewed_at
                ? formatDate(snapshot.flashcard_last_reviewed_at)
                : "—"
            }
            href="/flashcards"
            loading={progress.isLoading}
          />
        </div>
      </div>

      <div>
        <h2 className="text-sm font-medium text-muted-foreground">Rendimiento</h2>
        {progress.isLoading ? (
          <Loader label="Cargando rendimiento…" className="mt-1" />
        ) : (
          <p className="mt-1 text-xs text-muted-foreground">
            {snapshot?.attempt_count
              ? `${snapshot.attempt_count} ${snapshot.attempt_count === 1 ? "intento" : "intentos"} en ${snapshot.exams_taken} ${snapshot.exams_taken === 1 ? "examen" : "exámenes"}`
              : "Cuando hagas un examen, aquí verás promedio y evolución — no solo cuántos hay."}
          </p>
        )}
        <div className="mt-3 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat title="Hechos" value={snapshot?.exams_taken ?? 0} href="/exams" loading={progress.isLoading} />
          <Stat title="Promedio" value={formatScore(snapshot?.average_score)} href="/exams" loading={progress.isLoading} />
          <Stat title="Mejor nota" value={formatScore(snapshot?.best_score)} href="/exams" loading={progress.isLoading} />
          <Stat title="Última nota" value={formatScore(snapshot?.last_score)} href="/exams" loading={progress.isLoading} />
        </div>
      </div>

      {progress.isLoading ? (
        <Loader label="Cargando actividad reciente…" className="py-6" />
      ) : snapshot?.recent.length ? (
        <Card>
          <CardTitle>Actividad reciente</CardTitle>
          <CardDescription>Abre un intento para ver tus respuestas y la corrección.</CardDescription>
          <ul className="mt-4 space-y-1">
            {snapshot.recent.map((item) => (
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
      ) : (
        <Card>
          <CardTitle>Siguiente paso</CardTitle>
          <CardDescription>
            {canCreateContent(me.data)
              ? "Sube un documento. Cuando esté listo, genera un examen y el progreso aparecerá aquí."
              : "Cuando un administrador te asigne un examen, el progreso aparecerá aquí."}
          </CardDescription>
          <div className="mt-5">
            <Link href={canCreateContent(me.data) ? "/documents" : "/exams"}>
              <Button>{canCreateContent(me.data) ? "Ir a documentos" : "Ir a exámenes"}</Button>
            </Link>
          </div>
        </Card>
      )}
    </div>
  );
}

function Stat({
  title,
  value,
  href,
  loading = false,
}: {
  title: string;
  value: string | number;
  href: string;
  loading?: boolean;
}) {
  return (
    <Link
      href={href}
      className="rounded-xl border border-border bg-card p-5 shadow-sm transition-colors hover:border-accent hover:bg-muted"
    >
      <p className="text-sm text-muted-foreground">{title}</p>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-16" />
      ) : (
        <p className="mt-2 text-2xl font-semibold tracking-tight">{value}</p>
      )}
    </Link>
  );
}
