"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/error-state";
import { PageLoader } from "@/components/ui/loader";
import { surfaceListClass } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { formatDateTime } from "@/lib/utils";
import type { Appeal } from "@/types/api";

export default function MyAppealsPage() {
  const { t, locale } = useI18n();
  const appeals = useQuery({
    queryKey: ["appeals", "mine"],
    queryFn: () => apiFetch<Appeal[]>("/api/v1/appeals"),
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("appeals.title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("appeals.body")}</p>
      </div>

      {appeals.isLoading ? <PageLoader label={t("appeals.loading")} /> : null}
      {appeals.isError ? (
        <ErrorState
          title={t("appeals.loadError")}
          error={appeals.error}
          onRetry={() => void appeals.refetch()}
        />
      ) : null}

      {appeals.data?.length ? (
        <ul className={surfaceListClass}>
          {appeals.data.map((item) => (
            <li key={item.id} className="flex flex-wrap items-start justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-foreground">{item.exam_title}</p>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{item.question_prompt}</p>
                <p className="mt-1 text-xs text-muted-foreground">{formatDateTime(item.created_at, locale)}</p>
              </div>
              <div className="flex items-center gap-2">
                <Badge>{t(`appeals.status.${item.status}`)}</Badge>
                <Link href={`/appeals/${item.id}`} className="text-sm underline-offset-4 hover:underline">
                  {t("appeals.open")}
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : appeals.data ? (
        <EmptyState title={t("appeals.empty")} description={t("appeals.emptyBody")} />
      ) : null}
    </div>
  );
}
