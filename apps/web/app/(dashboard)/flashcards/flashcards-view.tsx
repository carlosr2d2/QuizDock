"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { DocumentCover } from "@/components/document-cover";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { listItemClass, surfaceListClass } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { ListLoader, Loader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { canCreateContent } from "@/lib/permissions";
import { cn, formatDateTime } from "@/lib/utils";
import type { Flashcard, FlashcardDeck, GenerationJob, User } from "@/types/api";

export function FlashcardsView() {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job");
  const documentId = searchParams.get("document");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [flipped, setFlipped] = useState(false);
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());

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

  const cardsPath = documentId
    ? `/api/v1/flashcards?document_id=${documentId}`
    : "/api/v1/flashcards";
  const cardsQuery = useQuery({
    queryKey: ["flashcards", documentId],
    queryFn: () => apiFetch<Flashcard[]>(cardsPath),
    refetchOnMount: "always",
  });

  const review = useMutation({
    mutationFn: ({ cardId, quality }: { cardId: string; quality: number }) =>
      apiFetch<Flashcard>(`/api/v1/flashcards/${cardId}/review`, {
        method: "POST",
        body: { quality },
      }),
    onSuccess: async (updated) => {
      setSeenIds((current) => new Set(current).add(updated.id));
      setFlipped(false);
      queryClient.setQueryData<Flashcard[]>(["flashcards", documentId], (current) =>
        (current ?? []).map((card) => (card.id === updated.id ? { ...card, ...updated } : card)),
      );
      await queryClient.invalidateQueries({ queryKey: ["flashcard-decks"] });
      await queryClient.invalidateQueries({ queryKey: ["progress"] });
    },
  });

  useEffect(() => {
    if (job.data?.status !== "succeeded") return;
    void queryClient.invalidateQueries({ queryKey: ["flashcard-decks"] });
    void queryClient.invalidateQueries({ queryKey: ["flashcards"] });
    void queryClient.invalidateQueries({ queryKey: ["credits"] });
    void queryClient.invalidateQueries({ queryKey: ["progress"] });
  }, [job.data?.status, queryClient]);

  useEffect(() => {
    setSelectedId(null);
    setFlipped(false);
  }, [documentId]);

  const decksLoading = decks.isLoading;
  const cards = cardsQuery.data ?? [];
  const generating = job.data?.status === "queued" || job.data?.status === "running";
  const totalDue = decks.data?.reduce((sum, deck) => sum + deck.due_count, 0) ?? 0;
  const totalCards = decks.data?.reduce((sum, deck) => sum + deck.card_count, 0) ?? 0;
  const selected = cards.find((card) => card.id === selectedId) ?? cards[0] ?? null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("flashcards.title")}</h1>
        {decksLoading ? (
          <Loader label={t("flashcards.loadingDecks")} className="mt-1" />
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            {t("flashcards.spaced")}
            {totalCards
              ? ` ${t("flashcards.dueLine", {
                  due: totalDue,
                  dueLabel: totalDue === 1 ? t("flashcards.pendingOne") : t("flashcards.pendingOther"),
                  total: totalCards,
                  cardLabel: totalCards === 1 ? t("overview.cardOne") : t("overview.cardOther"),
                })}`
              : canAuthor
                ? ` ${t("flashcards.authorHint")}`
                : ` ${t("flashcards.memberHint")}`}
          </p>
        )}
      </div>

      {jobId && job.isLoading ? (
        <Loader label={t("flashcards.checkingJob")} className="justify-center py-2" />
      ) : generating ? (
        <Loader label={t("flashcards.generating")} className="justify-center py-2" />
      ) : null}
      {job.data?.status === "failed" ? (
        <p className="text-sm text-destructive">{job.data.error_message ?? t("flashcards.generateFailed")}</p>
      ) : null}

      {cardsQuery.isError ? (
        <ErrorState
          title={t("flashcards.loadError")}
          error={cardsQuery.error}
          onRetry={() => void cardsQuery.refetch()}
        />
      ) : cardsQuery.isLoading && !generating ? (
        <Loader label={t("flashcards.loadingDue")} className="justify-center py-10" />
      ) : cards.length ? (
        <FlashcardStrip
          cards={cards}
          selectedId={selected?.id ?? null}
          flipped={flipped}
          seenIds={seenIds}
          reviewing={review.isPending}
          onSelect={(cardId) => {
            setSelectedId(cardId);
            setFlipped((open) => (cardId === selected?.id ? !open : false));
          }}
          onReview={(cardId, quality) => review.mutate({ cardId, quality })}
        />
      ) : decks.data?.length && !generating ? (
        <p className="text-sm text-muted-foreground">
          {documentId ? t("flashcards.deckUpToDate") : t("flashcards.noneDue")}
        </p>
      ) : !generating && !decks.isError && !decks.data?.length ? (
        <EmptyState
          title={t("flashcards.emptyTitle")}
          description={canAuthor ? t("flashcards.emptyAuthor") : t("flashcards.emptyMember")}
        >
          {canAuthor ? (
            <Link href="/documents">
              <Button variant="outline">{t("overview.goDocuments")}</Button>
            </Link>
          ) : null}
        </EmptyState>
      ) : null}

      {decks.isError ? (
        <ErrorState
          title={t("flashcards.loadError")}
          error={decks.error}
          onRetry={() => void decks.refetch()}
        />
      ) : decksLoading ? (
        <ListLoader rows={3} label={t("flashcards.loadingDecks")} />
      ) : decks.data && decks.data.length > 0 ? (
        <ul className={surfaceListClass}>
          {decks.data.map((deck) => {
            const href = deck.document_id ? `/flashcards?document=${deck.document_id}` : "/flashcards";
            const selectedDeck =
              (deck.document_id ?? "") === (documentId ?? "") && Boolean(documentId || !deck.document_id);
            return (
              <li key={deck.document_id ?? "none"} className={`flex items-center justify-between gap-4 ${listItemClass}`}>
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
                          {t("flashcards.dueLine", {
                            due: deck.due_count,
                            dueLabel: deck.due_count === 1 ? t("flashcards.pendingOne") : t("flashcards.pendingOther"),
                            total: deck.card_count,
                            cardLabel: deck.card_count === 1 ? t("overview.cardOne") : t("overview.cardOther"),
                          })}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">
                          {t("overview.upToDate", {
                            total: deck.card_count,
                            cardLabel: deck.card_count === 1 ? t("overview.cardOne") : t("overview.cardOther"),
                          })}
                        </span>
                      )}
                      {deck.last_reviewed_at
                        ? ` · ${t("flashcards.lastReviewed", { date: formatDateTime(deck.last_reviewed_at, locale) })}`
                        : ` · ${t("flashcards.notReviewed")}`}
                    </p>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {deck.due_count ? (
                    <Badge className="border-accent/30 bg-accent/10 text-accent">
                      {deck.due_count} {deck.due_count === 1 ? t("flashcards.pendingOne") : t("flashcards.pendingOther")}
                    </Badge>
                  ) : (
                    <Badge>{t("flashcards.caughtUpBadge")}</Badge>
                  )}
                  <Link href={href}>
                    <Button size="sm" variant={selectedDeck ? "primary" : "outline"}>
                      {deck.due_count ? t("flashcards.reviewDeck") : t("flashcards.viewDeck")}
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

function FlashcardStrip({
  cards,
  selectedId,
  flipped,
  seenIds,
  reviewing,
  onSelect,
  onReview,
}: {
  cards: Flashcard[];
  selectedId: string | null;
  flipped: boolean;
  seenIds: Set<string>;
  reviewing: boolean;
  onSelect: (cardId: string) => void;
  onReview: (cardId: string, quality: number) => void;
}) {
  const { t } = useI18n();
  const scrollerRef = useRef<HTMLDivElement>(null);
  const [canLeft, setCanLeft] = useState(false);
  const [canRight, setCanRight] = useState(false);

  function updateArrows() {
    const node = scrollerRef.current;
    if (!node) return;
    const max = node.scrollWidth - node.clientWidth;
    setCanLeft(node.scrollLeft > 8);
    setCanRight(max - node.scrollLeft > 8);
  }

  useEffect(() => {
    updateArrows();
    const node = scrollerRef.current;
    if (!node) return;
    const observer = new ResizeObserver(updateArrows);
    observer.observe(node);
    node.addEventListener("scroll", updateArrows, { passive: true });
    return () => {
      observer.disconnect();
      node.removeEventListener("scroll", updateArrows);
    };
  }, [cards.length]);

  function scrollByDirection(direction: 1 | -1) {
    const node = scrollerRef.current;
    if (!node) return;
    node.scrollBy({ left: direction * (node.clientWidth * 0.8), behavior: "smooth" });
  }

  return (
    <div className="relative">
      {canLeft ? (
        <button
          type="button"
          aria-label={t("flashcards.moreCards")}
          onClick={() => scrollByDirection(-1)}
          className="absolute left-0 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-card/95 text-foreground shadow-sm hover:bg-muted"
        >
          <ChevronLeft className="h-5 w-5" />
        </button>
      ) : null}
      <div
        ref={scrollerRef}
        className="flex gap-3 overflow-x-auto scroll-smooth pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {cards.map((card) => {
          const reviewed = Boolean(card.last_reviewed_at) || seenIds.has(card.id);
          const active = card.id === selectedId;
          const showBack = active && flipped;
          return (
            <div
              key={card.id}
              className={cn(
                "flex h-52 w-36 shrink-0 snap-start flex-col rounded-xl p-2.5 sm:h-56 sm:w-40",
                reviewed ? "bg-muted/50 text-muted-foreground" : "bg-accent/10",
                active && "bg-accent/30 text-foreground",
              )}
            >
              <div
                role="button"
                tabIndex={0}
                onClick={() => onSelect(card.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    onSelect(card.id);
                  }
                }}
                className="flex min-h-0 min-w-0 flex-1 cursor-pointer flex-col text-left"
              >
                <p className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {reviewed ? t("flashcards.reviewed") : showBack ? t("flashcards.answer") : t("flashcards.question")}
                </p>
                <div className="mt-1.5 min-h-0 flex-1 overflow-y-auto overscroll-contain pr-1 text-sm font-medium leading-snug break-words [overflow-wrap:anywhere]">
                  {showBack ? card.back : card.front}
                </div>
              </div>
              <div className="mt-2 grid shrink-0 grid-cols-2 gap-1">
                <button
                  type="button"
                  disabled={reviewing}
                  onClick={(event) => {
                    event.stopPropagation();
                    onReview(card.id, 1);
                  }}
                  className="h-7 rounded-md border border-border bg-background/80 px-1 text-[10px] font-medium hover:bg-muted disabled:opacity-50"
                >
                  {t("flashcards.hard")}
                </button>
                <button
                  type="button"
                  disabled={reviewing}
                  onClick={(event) => {
                    event.stopPropagation();
                    onReview(card.id, 5);
                  }}
                  className="h-7 rounded-md bg-accent px-1 text-[10px] font-medium text-accent-foreground hover:opacity-90 disabled:opacity-50"
                >
                  {t("flashcards.easy")}
                </button>
              </div>
            </div>
          );
        })}
      </div>
      {canRight ? (
        <button
          type="button"
          aria-label={t("flashcards.moreCards")}
          onClick={() => scrollByDirection(1)}
          className="absolute right-0 top-1/2 z-10 flex h-10 w-10 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-card/95 text-foreground shadow-sm hover:bg-muted"
        >
          <ChevronRight className="h-5 w-5" />
        </button>
      ) : null}
    </div>
  );
}
