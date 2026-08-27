"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { errorDetail, errorMessage, reportClientError } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export function ErrorState({
  title,
  error,
  onRetry,
  className,
}: {
  title: string;
  error?: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const t = useT();
  const [report, setReport] = useState<"idle" | "sending" | "sent" | "copied" | "failed">("idle");
  const message = errorMessage(error);
  const detail = errorDetail(error);

  async function sendReport() {
    setReport("sending");
    const sent = await reportClientError({
      path: typeof window !== "undefined" ? window.location.pathname : "/",
      message,
      detail,
    });
    if (sent) {
      setReport("sent");
      return;
    }
    try {
      await navigator.clipboard.writeText(
        `QuizDock error\n${typeof window !== "undefined" ? window.location.href : ""}\n${message}\n\n${detail}`,
      );
      setReport("copied");
    } catch {
      setReport("failed");
    }
  }

  const reportLabel =
    report === "sending"
      ? t("error.sending")
      : report === "sent"
        ? t("error.sent")
        : report === "copied"
          ? t("error.copied")
          : report === "failed"
            ? t("error.failed")
            : t("error.send");

  return (
    <div
      role="alert"
      className={cn(
        "rounded-xl border border-destructive/25 bg-destructive/5 px-6 py-10 text-center",
        className,
      )}
    >
      <p className="text-xs font-medium uppercase tracking-wide text-destructive">{t("common.error")}</p>
      <h3 className="mt-2 text-base font-semibold tracking-tight">{title}</h3>
      <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{message}</p>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        {onRetry ? (
          <Button type="button" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        ) : null}
        <Button
          type="button"
          variant={onRetry ? "outline" : "primary"}
          loading={report === "sending"}
          disabled={report === "sent" || report === "copied"}
          onClick={() => void sendReport()}
        >
          {reportLabel}
        </Button>
      </div>
      {report === "copied" ? (
        <p className="mt-3 text-xs text-muted-foreground">
          {t("error.copiedHint")}
        </p>
      ) : null}
    </div>
  );
}
