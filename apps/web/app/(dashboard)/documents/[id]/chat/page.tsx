"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { PageLoader, Loader } from "@/components/ui/loader";
import { apiFetch } from "@/lib/api";
import type { Locale } from "@/lib/i18n/config";
import { useI18n } from "@/lib/i18n/provider";
import { cn, formatDateTime } from "@/lib/utils";
import type { ChatMessage, ChatSession, ChatSessionDetail, CreditBalance, Document } from "@/types/api";

export default function DocumentChatPage() {
  const { t, locale } = useI18n();
  const params = useParams<{ id: string }>();
  const documentId = params.id;
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const document = useQuery({
    queryKey: ["documents", documentId],
    queryFn: () => apiFetch<Document>(`/api/v1/documents/${documentId}`),
  });
  const credits = useQuery({
    queryKey: ["credits"],
    queryFn: () => apiFetch<CreditBalance>("/api/v1/billing/credits"),
  });
  const sessions = useQuery({
    queryKey: ["document-chat-sessions", documentId],
    queryFn: () => apiFetch<ChatSession[]>(`/api/v1/documents/${documentId}/chat/sessions`),
    enabled: Boolean(documentId),
  });
  const detail = useQuery({
    queryKey: ["document-chat", documentId, sessionId],
    queryFn: () =>
      apiFetch<ChatSessionDetail>(`/api/v1/documents/${documentId}/chat/sessions/${sessionId}`),
    enabled: Boolean(documentId && sessionId),
  });

  useEffect(() => {
    if (sessionId || !sessions.data?.length) return;
    setSessionId(sessions.data[0].id);
  }, [sessionId, sessions.data]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail.data?.messages?.length]);

  const createSession = useMutation({
    mutationFn: () =>
      apiFetch<ChatSession>(`/api/v1/documents/${documentId}/chat/sessions`, {
        method: "POST",
        body: {},
      }),
    onSuccess: async (session) => {
      setSessionId(session.id);
      setError(null);
      await queryClient.invalidateQueries({ queryKey: ["document-chat-sessions", documentId] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const send = useMutation({
    mutationFn: async (content: string) => {
      let activeId = sessionId;
      if (!activeId) {
        const session = await apiFetch<ChatSession>(`/api/v1/documents/${documentId}/chat/sessions`, {
          method: "POST",
          body: {},
        });
        activeId = session.id;
        await queryClient.invalidateQueries({ queryKey: ["document-chat-sessions", documentId] });
      }
      const message = await apiFetch<ChatMessage>(
        `/api/v1/documents/${documentId}/chat/sessions/${activeId}/messages`,
        {
          method: "POST",
          body: { content },
        },
      );
      return { message, sessionId: activeId };
    },
    onSuccess: async (result) => {
      setDraft("");
      setError(null);
      setSessionId(result.sessionId);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["document-chat", documentId, result.sessionId] }),
        queryClient.invalidateQueries({ queryKey: ["credits"] }),
      ]);
    },
    onError: (err: Error) => setError(err.message),
  });

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const content = draft.trim();
    if (!content || send.isPending) return;
    send.mutate(content);
  }

  if (document.isLoading) {
    return <PageLoader label={t("chat.loading")} />;
  }
  if (document.isError || !document.data) {
    return (
      <ErrorState
        title={t("chat.loadError")}
        error={document.error}
        onRetry={() => void document.refetch()}
      />
    );
  }

  const title = document.data.title || document.data.filename;
  const messages = detail.data?.messages ?? [];
  const cost = 1;

  return (
    <div className="mx-auto flex h-[calc(100vh-6rem)] max-w-3xl flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">{t("chat.eyebrow")}</p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("chat.costHint", { cost, balance: credits.data?.balance ?? "—" })}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            loading={createSession.isPending}
            onClick={() => createSession.mutate()}
          >
            {t("chat.newConversation")}
          </Button>
          <Link href="/documents">
            <Button type="button" variant="ghost" size="sm">
              {t("chat.backDocuments")}
            </Button>
          </Link>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-border bg-card">
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          {!sessionId && !messages.length ? (
            <p className="text-sm text-muted-foreground">{t("chat.empty")}</p>
          ) : null}
          {messages.map((message) => (
            <ChatBubble key={message.id} message={message} locale={locale} />
          ))}
          {send.isPending ? (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader className="h-4 w-4" />
              {t("chat.thinking")}
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={onSubmit} className="border-t border-border p-3">
          {error ? <p className="mb-2 text-sm text-destructive">{error}</p> : null}
          <div className="flex gap-2">
            <Input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder={t("chat.placeholder")}
              disabled={send.isPending}
              className="flex-1"
            />
            <Button type="submit" disabled={!draft.trim()} loading={send.isPending}>
              {t("chat.send")}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function ChatBubble({ message, locale }: { message: ChatMessage; locale: Locale }) {
  const { t } = useI18n();
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm",
          isUser ? "bg-accent text-accent-foreground" : "bg-muted/60 text-foreground",
          message.refusal && "border border-destructive/30 bg-destructive/5",
        )}
      >
        <p className="min-w-0 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
          {message.content}
        </p>
        {!isUser && message.citations?.length ? (
          <div className="mt-3 space-y-2 border-t border-border/60 pt-2">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              {t("chat.citations")}
            </p>
            {message.citations.map((citation, index) => (
              <blockquote
                key={`${message.id}-${index}`}
                className="border-l-2 border-accent/40 pl-2 text-xs text-muted-foreground"
              >
                <p className="italic text-foreground/90">{citation.quote}</p>
                <p className="mt-1">
                  {citation.page_start != null
                    ? t("chat.pageLabel", { page: citation.page_start })
                    : t("exams.pageUnavailable")}
                  {citation.chapter ? ` · ${citation.chapter}` : ""}
                </p>
              </blockquote>
            ))}
          </div>
        ) : null}
        <p className="mt-1 text-[10px] opacity-70">{formatDateTime(message.created_at, locale)}</p>
      </div>
    </div>
  );
}
