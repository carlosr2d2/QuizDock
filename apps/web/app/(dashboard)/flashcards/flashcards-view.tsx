"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { DocumentCover } from "@/components/document-cover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ListLoader, Loader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { canCreateContent } from "@/lib/permissions";
import { cn, formatDateTime } from "@/lib/utils";
import type { Flashcard, FlashcardDeck, GenerationJob, User } from "@/types/api";

export function FlashcardsView() {
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job");
  const documentId = searchParams.get("document");
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);

  const job = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => apiFetch<GenerationJob>(`/api/v1/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 2500 : false;
    },
  });

  const decks = useQuery({
    queryKey: ["flashcard-decks"],
    queryFn: () => apiFetch<FlashcardDeck[]>("/api/v1/flashcards/decks"),
    refetchOnMount: "always",
  });
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<User>("/api/v1/auth/me"),
  });
  const canAuthor = canCreateContent(me.data);

  const duePath = documentId
    ? `/api/v1/flashcards?due=true&document_id=${documentId}`
    : "/api/v1/flashcards?due=true";
  const due = useQuery({
    queryKey: ["flashcards-due", documentId],
    queryFn: () => apiFetch<Flashcard[]>(duePath),
    refetchOnMount: "always",
  });

  const review = useMutation({
    mutationFn: ({ cardId, quality }: { cardId: string; quality: number }) =>
      apiFetch<Flashcard>(`/api/v1/flashcards/${cardId}/review`, {
        method: "POST",
        body: { quality },
      }),
    onSuccess: async () => {
      setFlipped(false);
      setIndex(0);
      await queryClient.invalidateQueries({ queryKey: ["flashcards-due"] });
      await queryClient.invalidateQueries({ queryKey: ["flashcard-decks"] });
      await queryClient.invalidateQueries({ queryKey: ["progress"] });
    },
  });

  useEffect(() => {
    if (job.data?.status !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: ["flashcard-decks"] });
    void queryClient.invalidateQueries({ queryKey: ["flashcards-due"] });
    void queryClient.invalidateQueries({ queryKey: ["credits"] });
    void queryClient.invalidateQueries({ queryKey: ["progress"] });
  }, [job.data?.status, queryClient]);

  const decksLoading = decks.isLoading;
  const dueLoading = due.isLoading;
  const queue = due.data ?? [];
  const current = queue[index] ?? queue[0];
  const generating = job.data?.status === "queued" || job.data?.status === "running";
  const activeDeck = decks.data?.find((deck) => (deck.document_id ?? "") === (documentId ?? ""));
  const totalDue = decks.data?.reduce((sum, deck) => sum + deck.due_count, 0) ?? 0;
  const totalCards = decks.data?.reduce((sum, deck) => sum + deck.card_count, 0) ?? 0;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Flashcards</h1>
        {decksLoading ? (
          <Loader label="Cargando mazos…" className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            Repaso con repetición espaciada (SM-2).
            {totalCards
              ? ` ${totalDue} ${totalDue === 1 ? "pendiente" : "pendientes"} · ${totalCards} ${totalCards === 1 ? "tarjeta" : "tarjetas"}`
              : canAuthor
                ? " Genera un mazo desde un documento listo."
                : " Un administrador genera los mazos; tú repasas las tarjetas."}
          </p>
        )}
      </div>

      {jobId && job.isLoading ? (
        <Loader label="Consultando generación…" className="justify-center py-2" />
      ) : generating ? (
        <Loader label="Generando tarjetas… esta vista se actualiza sola." className="justify-center py-2" />
      ) : null}
      {job.data?.status === "failed" ? (
        <p className="text-sm text-destructive">{job.data.error_message ?? "La generación falló."}</p>
      ) : null}

      {dueLoading && !current && !generating ? (
        <Loader label="Cargando tarjetas pendientes…" className="justify-center py-10" />
      ) : current ? (
        <div className="mx-auto max-w-xl space-y-4">
          {activeDeck || current.document_title ? (
            <p className="text-center text-xs text-muted-foreground">
              {activeDeck?.document_title ?? current.document_title}
            </p>
          ) : null}
          <button
            type="button"
            onClick={() => setFlipped((value) => !value)}
            className={cn(
              "w-full rounded-xl border px-6 py-16 text-center shadow-sm transition-colors",
              flipped
                ? "border-accent bg-accent/15 hover:bg-accent/20"
                : "border-border bg-card hover:border-accent/50 hover:bg-muted",
            )}
          >
            <p className="text-xs uppercase tracking-wide text-muted-foreground">
              {flipped ? "Respuesta" : "Pregunta"}
            </p>
            <p className="mt-3 text-base font-medium">{flipped ? current.back : current.front}</p>
          </button>
          {flipped ? (
            <div className="flex justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => review.mutate({ cardId: current.id, quality: 1 })}
                loading={review.isPending}
              >
                Otra vez
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => review.mutate({ cardId: current.id, quality: 3 })}
                loading={review.isPending}
              >
                Bien
              </Button>
              <Button size="sm" onClick={() => review.mutate({ cardId: current.id, quality: 5 })} loading={review.isPending}>
                Fácil
              </Button>
            </div>
          ) : (
            <p className="text-center text-xs text-muted-foreground">
              {Math.min(index + 1, queue.length)} / {queue.length} pendientes · pulsa la tarjeta para revelar
            </p>
          )}
        </div>
      ) : decks.data?.length && !generating ? (
        <p className="text-sm text-muted-foreground">
          {documentId ? "Este mazo está al día." : "No hay tarjetas pendientes de repaso ahora."}
        </p>
      ) : !generating && !decks.isError && !decks.data?.length ? (
        <EmptyState
          title="No hay tarjetas"
          description={
            canAuthor
              ? "Genera un mazo desde un documento listo. El coste es 1 crédito por tarjeta."
              : "Cuando un administrador genere un mazo, podrás repasarlo aquí."
          }
        >
          {canAuthor ? (
            <Link href="/documents">
              <Button variant="outline">Ir a documentos</Button>
            </Link>
          ) : null}
        </EmptyState>
      ) : null}

      {decks.isError ? (
        <ErrorState
          title="No se pudieron cargar las flashcards"
          error={decks.error}
          onRetry={() => void decks.refetch()}
        />
      ) : decksLoading ? (
        <ListLoader rows={3} label="Cargando mazos…" />
      ) : decks.data && decks.data.length > 0 ? (
        <ul className={surfaceListClass}>
          {decks.data.map((deck) => {
            const href = deck.document_id ? `/flashcards?document=${deck.document_id}` : "/flashcards";
            const selected = (deck.document_id ?? "") === (documentId ?? "") && Boolean(documentId || !deck.document_id);
            return (
              <li key={deck.document_id ?? "none"} className="flex items-center justify-between gap-4 px-5 py-4">
                <div className="flex min-w-0 items-center gap-4">
                  <DocumentCover
                    documentId={deck.document_id}
                    hasCover={deck.has_cover}
                    kind={deck.document_kind}
                    title={deck.document_title}
                  />
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{deck.document_title}</p>
                    <p className="mt-1 text-xs">
                      {deck.due_count ? (
                        <span className="text-accent">
                          {deck.due_count} {deck.due_count === 1 ? "pendiente" : "pendientes"} · {deck.card_count}{" "}
                          {deck.card_count === 1 ? "tarjeta" : "tarjetas"}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">
                          Al día · {deck.card_count} {deck.card_count === 1 ? "tarjeta" : "tarjetas"}
                        </span>
                      )}
                      {deck.last_reviewed_at
                        ? ` · último ${formatDateTime(deck.last_reviewed_at)}`
                        : " · aún no repasadas"}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {deck.due_count ? (
                    <Badge className="border-accent/30 bg-accent/10 text-accent">
                      {deck.due_count} {deck.due_count === 1 ? "pendiente" : "pendientes"}
                    </Badge>
                  ) : (
                    <Badge>al día</Badge>
                  )}
                  <Link href={href}>
                    <Button size="sm" variant={selected && deck.due_count ? "primary" : "outline"}>
                      {deck.due_count ? "Repasar" : "Ver mazo"}
                    </Button>
                  </Link>
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
