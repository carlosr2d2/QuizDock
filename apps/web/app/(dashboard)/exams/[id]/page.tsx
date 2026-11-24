"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { AppealCta } from "@/components/appeal-cta";
import { DocumentCover } from "@/components/document-cover";
import { AttemptHistoryCard, AttemptRow } from "@/components/attempt-row";
import { EvidencePanel } from "@/components/evidence-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardDescription, CardTitle } from "@/components/ui/card";
import { checkboxClass } from "@/components/ui/input";
import { PageLoader, Loader, ProgressBar } from "@/components/ui/loader";
import { ErrorState } from "@/components/ui/error-state";
import { apiDownload, apiFetch } from "@/lib/api";
import { useI18n, useT } from "@/lib/i18n/provider";
import { cn, formatDateTime, formatScore } from "@/lib/utils";
import type {
  Appeal,
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
  const t = useT();
  return (
    <Suspense fallback={<PageLoader label={t("exams.loadingExam")} />}>
      <ExamPlayer />
    </Suspense>
  );
}

function ExamPlayer() {
  const { t, locale } = useI18n();
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

  const myAppeals = useQuery({
    queryKey: ["appeals", "mine"],
    queryFn: () => apiFetch<Appeal[]>("/api/v1/appeals"),
    enabled: Boolean(result?.is_own),
  });

  const appealsByQuestion = useMemo(() => {
    const map = new Map<string, Appeal>();
    for (const item of myAppeals.data ?? []) {
      if (result && item.attempt_id === result.id) {
        map.set(item.question_id, item);
      }
    }
    return map;
  }, [myAppeals.data, result]);

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
    return <PageLoader label={t("exams.loadingExam")} />;
  }
  if (exam.error || !exam.data) {
    return (
      <ErrorState
        title={t("exams.openError")}
        error={exam.error ?? new Error(t("exams.notFound"))}
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
        size="md"
      />
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{data.title}</h1>
        {data.document_title && data.document_title !== data.title ? (
          <p className="mt-1 text-sm text-muted-foreground">{data.document_title}</p>
        ) : null}
        {data.attempt_count ? (
          <p className="mt-1 text-sm text-muted-foreground">
            {t("exams.lastScore", {
              score: formatScore(data.last_score),
              count: data.attempt_count,
              attemptLabel: data.attempt_count === 1 ? t("overview.attemptOne") : t("overview.attemptOther"),
            })}
          </p>
        ) : null}
        {data.assigned_to_me && data.assignment_status === "pending" ? (
          <p className="mt-1 text-sm text-accent">{t("exams.assignedPending")}</p>
        ) : null}
        {data.status === "ready" ? <ExamPdfActions exam={data} /> : null}
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
    const done = data.generated_count ?? 0;
    const working = Math.min(done < total ? done + 1 : total, total);
    return (
      <div className="space-y-6">
        <Badge>{t("status.generating")}</Badge>
        {heading}
        <div className="max-w-lg rounded-xl border border-border bg-card p-5">
          <p className="text-3xl font-semibold tabular-nums tracking-tight">
            {t("common.of", { current: working, total })}
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            {t("exams.creatingQuestion", { current: working, total })}
          </p>
          <ProgressBar
            className="mt-4"
            value={working}
            max={total}
            label={t("exams.generatingHint")}
            showValue={false}
          />
        </div>
      </div>
    );
  }

  if (data.status === "failed") {
    return (
      <div className="space-y-3">
        <Badge>{t("status.failed")}</Badge>
        {heading}
        <p className="text-sm text-destructive">
          {data.error_message ?? t("exams.generateFailed")}
        </p>
        <Link href="/documents" className="text-sm underline-offset-4 hover:underline">
          {t("exams.backDocuments")}
        </Link>
      </div>
    );
  }

  if (!taking && targetAttemptId && !result) {
    return (
      <div className="space-y-3">
        {heading}
        {assignPanel}
        <PageLoader label={t("exams.loadingAttempt")} />
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
              {result.is_own ? t("exams.yourResult") : t("exams.answersOf", { name: result.full_name || result.email })}
            </p>
            <h2 className="mt-1 text-2xl font-semibold tracking-tight">{formatScore(result.score)}</h2>
            <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(result.completed_at, locale)}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {result.is_own ? (
              <Button type="button" onClick={redo}>
                {t("exams.redo")}
              </Button>
            ) : null}
            <Link href="/exams">
              <Button variant="outline">{t("exams.backExams")}</Button>
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
            <li
              key={item.question_id}
              className={cn(
                "rounded-xl border p-5",
                item.is_correct
                  ? "border-accent/30 bg-accent/10"
                  : "border-destructive/30 bg-destructive/10",
              )}
            >
              <QuestionHeader index={index + 1} prompt={item.prompt} kind={item.kind} />
              <p className={cn("mt-2 text-sm", item.is_correct ? "text-accent" : "text-destructive")}>
                {item.is_correct ? t("exams.correct") : t("exams.incorrect")}
              </p>
              <AttemptAnswer item={item} />
              <EvidencePanel
                evidence={item.evidence}
                explanation={item.explanation}
                locale={locale}
              />
              {result.is_own && !item.is_correct ? (
                <AppealCta
                  attemptId={result.id}
                  questionId={item.question_id}
                  documentId={data.document_id}
                  existing={appealsByQuestion.get(item.question_id) ?? null}
                />
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
          {t("exams.mixHint", { count: data.questions.length })}
          {history.length ? t("exams.redoFree") : ""}
        </p>
      <AttemptHistory attempts={history} onSelect={viewAttempt} />
      {openAttempt.error ? (
        <p className="text-sm text-destructive">{openAttempt.error.message}</p>
      ) : null}

      <ol className="space-y-6">
        {data.questions.map((question, index) => (
          <li key={question.id} className="rounded-xl border border-border bg-card p-5">
            <QuestionHeader index={index + 1} prompt={question.prompt} kind={question.kind} />
            {question.kind === "multiple_choice" ? (
              <p className="mt-2 text-xs text-muted-foreground">{t("exams.selectAll")}</p>
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
        {submit.isPending ? t("exams.submitting") : data.attempt_count ? t("exams.submitAgain") : t("exams.submit")}
      </Button>
    </form>
    </div>
  );
}

const wrapTextClass = "min-w-0 break-words [overflow-wrap:anywhere]";

function QuestionHeader({
  index,
  prompt,
  kind,
}: {
  index: number;
  prompt: string;
  kind: QuestionKind | string | undefined;
}) {
  const t = useT();
  return (
    <div className="flex items-start gap-3">
      <p className={cn("flex-1 text-sm font-medium", wrapTextClass)}>
        {index}. {prompt}
      </p>
      <Badge className="shrink-0">{questionKindLabel(kind, t)}</Badge>
    </div>
  );
}

function questionKindLabel(kind: QuestionKind | string | undefined, t: (key: string) => string) {
  switch (kind) {
    case "true_false":
      return t("exams.trueFalse");
    case "multiple_choice":
      return t("exams.multiCorrect");
    default:
      return t("exams.singleChoice");
  }
}

function selectedIndices(value: number | number[] | undefined): number[] {
  if (Array.isArray(value)) return value;
  if (typeof value === "number") return [value];
  return [];
}

function formatChoices(options: string[], indices: number[], empty: string) {
  if (!indices.length) return empty;
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
          className={cn(
            "flex cursor-pointer items-start gap-3 rounded-md border border-transparent px-2 py-2 transition-colors duration-200 hover:bg-muted/60",
            (multi ? selected.includes(optionIndex) : value === optionIndex) && "border-accent/30 bg-accent/10",
          )}
        >
          <input
            type={multi ? "checkbox" : "radio"}
            className={cn("mt-1", checkboxClass)}
            name={question.id}
            checked={multi ? selected.includes(optionIndex) : value === optionIndex}
            onChange={() => (multi ? toggle(optionIndex) : onChange(optionIndex))}
            required={!multi}
          />
          <span className={cn("flex-1 text-sm", wrapTextClass)}>{option}</span>
        </label>
      ))}
    </fieldset>
  );
}

function AttemptAnswer({ item }: { item: QuestionResult }) {
  const t = useT();
  const selected = item.selected_indices?.length
    ? item.selected_indices
    : item.selected_index != null
      ? [item.selected_index]
      : [];
  const correct = item.correct_indices?.length ? item.correct_indices : [item.correct_index];
  const empty = t("exams.noAnswer");
  if (item.is_correct) {
    return (
      <p className={cn("mt-2 text-sm text-muted-foreground", wrapTextClass)}>
        {t("exams.yourAnswer", { answer: formatChoices(item.options, selected, empty) })}
      </p>
    );
  }
  return (
    <div className="mt-2 space-y-1 text-sm text-muted-foreground">
      <p className={wrapTextClass}>
        {t("exams.yourAnswer", { answer: formatChoices(item.options, selected, empty) })}
      </p>
      <p className={wrapTextClass}>
        {t("exams.correctChoice", { answer: formatChoices(item.options, correct, empty) })}
      </p>
    </div>
  );
}

function ExamPdfActions({ exam }: { exam: ExamDetail }) {
  const t = useT();
  const queryClient = useQueryClient();
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (allow_pdf_download: boolean) =>
      apiFetch<ExamDetail>(`/api/v1/exams/${exam.id}`, {
        method: "PATCH",
        body: { allow_pdf_download },
      }),
    onSuccess: (data) => {
      queryClient.setQueryData(["exam", exam.id], data);
      void queryClient.invalidateQueries({ queryKey: ["exams"] });
    },
  });
  const download = useMutation({
    mutationFn: () => apiDownload(`/api/v1/exams/${exam.id}/pdf`),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${exam.title || "examen"}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    },
    onError: (error: Error) => setDownloadError(error.message),
  });

  if (!exam.can_assign && !exam.can_download_pdf) return null;

  return (
    <div className="mt-3 space-y-2">
      {exam.can_assign ? (
        <label className="flex max-w-xl cursor-pointer items-start gap-2 text-sm">
          <input
            type="checkbox"
            className={cn("mt-1", checkboxClass)}
            checked={Boolean(exam.allow_pdf_download)}
            disabled={save.isPending}
            onChange={(event) => save.mutate(event.target.checked)}
          />
          <span>
            {t("exams.allowPdfDownload")}
            <span className="mt-0.5 block text-xs text-muted-foreground">{t("exams.allowPdfDownloadHint")}</span>
          </span>
        </label>
      ) : null}
      {exam.can_download_pdf ? (
        <Button
          type="button"
          variant="outline"
          size="sm"
          loading={download.isPending}
          onClick={() => {
            setDownloadError(null);
            download.mutate();
          }}
        >
          {download.isPending ? t("exams.downloadingPdf") : t("exams.downloadPdf")}
        </Button>
      ) : null}
      {downloadError ? <p className="text-sm text-destructive">{downloadError}</p> : null}
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
  const { t, locale } = useI18n();
  if (!attempts.length) return null;
  return (
    <AttemptHistoryCard description={t("exams.historyBody")}>
      {attempts.map((item, index) => (
        <li key={item.id}>
          <AttemptRow
            title={t("exams.attemptN", { n: attempts.length - index })}
            subtitle={formatDateTime(item.completed_at, locale)}
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
  const t = useT();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<string[]>([]);
  const team = useQuery({
    queryKey: ["team"],
    queryFn: () => apiFetch<TeamSnapshot>("/api/v1/organizations/current/team"),
  });
  const assign = useMutation({
    mutationFn: (body: { user_ids?: string[]; group_ids?: string[]; all_members?: boolean }) =>
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
      <CardTitle>{t("exams.assignEmployees")}</CardTitle>
      <CardDescription>{t("exams.assignEmployeesBody")}</CardDescription>
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
                    actionLabel={t("exams.viewAnswers")}
                    onClick={() => onViewAttempt(item.last_attempt_id!)}
                  />
                ) : (
                  <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">{item.full_name}</p>
                      <p className="text-xs text-muted-foreground">{item.email}</p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <Badge>{t("common.pending")}</Badge>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => unassign.mutate(item.user_id)}
                        loading={unassign.isPending && unassign.variables === item.user_id}
                      >
                        {t("team.remove")}
                      </Button>
                    </div>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-muted-foreground">{t("exams.nobodyAssigned")}</p>
      )}
      {team.isLoading ? (
        <Loader label={t("exams.loadingMembers")} className="mt-4" />
      ) : (
        <>
          {(team.data?.groups ?? []).length ? (
            <div className="mt-4 space-y-2">
              <p className="text-sm font-medium">{t("nav.groups")}</p>
              <ul className="space-y-2">
                {(team.data?.groups ?? []).map((group) => {
                  const already = (exam.assigned_group_ids ?? []).includes(group.id);
                  const empty = group.member_count === 0;
                  return (
                    <li
                      key={group.id}
                      className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{group.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {group.member_count}{" "}
                          {group.member_count === 1 ? t("exams.memberOne") : t("exams.memberOther")}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant={already ? "outline" : "primary"}
                        disabled={already || empty}
                        loading={assign.isPending && assign.variables?.group_ids?.[0] === group.id}
                        onClick={() => assign.mutate({ group_ids: [group.id] })}
                      >
                        {already ? t("exams.alreadyAssigned") : empty ? t("exams.emptyGroup") : t("exams.assignGroup")}
                      </Button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : null}
          {available.length ? (
            <div className="mt-4 space-y-3">
              <p className="text-sm font-medium">{t("exams.people")}</p>
              <ul className="space-y-2">
            {available.map((member) => (
              <li key={member.user_id}>
                <label className="flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 text-sm transition-colors duration-200 hover:bg-muted/60">
                  <input
                    type="checkbox"
                    className={checkboxClass}
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
              {assign.isPending ? t("exams.assigning") : t("exams.assignSelected")}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => assign.mutate({ all_members: true })}
              loading={assign.isPending}
            >
              {assign.isPending ? t("exams.assigning") : t("exams.assignAll")}
            </Button>
          </div>
            </div>
          ) : team.data && !available.length ? (
            <p className="mt-3 text-sm text-muted-foreground">{t("exams.allAssigned")}</p>
          ) : null}
        </>
      )}
      {assign.error ? <p className="mt-3 text-sm text-destructive">{assign.error.message}</p> : null}
    </Card>
  );
}
