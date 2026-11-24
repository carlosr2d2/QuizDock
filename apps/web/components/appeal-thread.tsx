"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { apiFetch, apiUpload } from "@/lib/api";
import { useI18n } from "@/lib/i18n/provider";
import { formatDateTime } from "@/lib/utils";
import type { AppealAttachment, AppealDetail } from "@/types/api";

type AppealThreadProps = {
  appealId: string;
  detail: AppealDetail;
  canComment: boolean;
};

export function AppealThread({ appealId, detail, canComment }: AppealThreadProps) {
  const { t, locale } = useI18n();
  const queryClient = useQueryClient();
  const [body, setBody] = useState("");
  const [attachments, setAttachments] = useState<AppealAttachment[]>([]);
  const [uploading, setUploading] = useState(false);

  const comment = useMutation({
    mutationFn: () =>
      apiFetch<AppealDetail>(`/api/v1/appeals/${appealId}/comments`, {
        method: "POST",
        body: {
          body,
          attachment_keys: attachments.map((item) => item.storage_key),
        },
      }),
    onSuccess: async () => {
      setBody("");
      setAttachments([]);
      await queryClient.invalidateQueries({ queryKey: ["appeals", appealId] });
      await queryClient.invalidateQueries({ queryKey: ["appeals"] });
    },
  });

  async function onPickFile(file: File | null) {
    if (!file || attachments.length >= 3) return;
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const uploaded = await apiUpload<AppealAttachment>(
        `/api/v1/appeals/${appealId}/attachments`,
        form,
      );
      setAttachments((current) => [...current, uploaded].slice(0, 3));
    } catch (error) {
      comment.reset();
      throw error;
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-5">
      <div>
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {t("appeals.thread")}
        </p>
        <p className="mt-1 text-sm text-muted-foreground">{t("appeals.threadHint")}</p>
      </div>

      {detail.comments?.length ? (
        <ul className="space-y-3">
          {detail.comments.map((item) => (
            <li key={item.id} className="rounded-lg border border-border/70 bg-background/60 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-sm font-medium text-foreground">
                  {item.author_name || item.author_email || t("appeals.unknownAuthor")}
                </p>
                <p className="text-xs text-muted-foreground">{formatDateTime(item.created_at, locale)}</p>
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm text-foreground">{item.body}</p>
              {item.attachment_keys?.length ? (
                <ul className="mt-2 space-y-1">
                  {item.attachment_keys.map((key) => (
                    <li key={key} className="truncate text-xs text-muted-foreground">
                      {t("appeals.attachment")}: {key.split("/").pop()}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{t("appeals.threadEmpty")}</p>
      )}

      {canComment ? (
        <div className="space-y-3 border-t border-border pt-3">
          <textarea
            className="min-h-24 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={body}
            onChange={(event) => setBody(event.target.value)}
            placeholder={t("appeals.commentPlaceholder")}
            maxLength={4000}
          />
          <div className="flex flex-wrap items-center gap-2">
            <label className="inline-flex cursor-pointer items-center rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted">
              {uploading ? t("appeals.uploading") : t("appeals.addAttachment")}
              <input
                type="file"
                className="hidden"
                accept=".pdf,.png,.jpg,.jpeg,.txt,application/pdf,image/png,image/jpeg,text/plain"
                disabled={uploading || attachments.length >= 3 || comment.isPending}
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  event.target.value = "";
                  void onPickFile(file).catch((error: Error) => {
                    comment.reset();
                    window.alert(error.message);
                  });
                }}
              />
            </label>
            <p className="text-xs text-muted-foreground">{t("appeals.attachmentHint")}</p>
          </div>
          {attachments.length ? (
            <ul className="space-y-1">
              {attachments.map((item) => (
                <li key={item.storage_key} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate text-muted-foreground">
                    {item.filename} · {Math.max(1, Math.round(item.size / 1024))} KB
                  </span>
                  <button
                    type="button"
                    className="text-destructive underline-offset-4 hover:underline"
                    onClick={() =>
                      setAttachments((current) =>
                        current.filter((row) => row.storage_key !== item.storage_key),
                      )
                    }
                  >
                    {t("common.remove")}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
          {comment.error ? <p className="text-sm text-destructive">{comment.error.message}</p> : null}
          <Button
            type="button"
            size="sm"
            loading={comment.isPending}
            disabled={body.trim().length < 1 || uploading}
            onClick={() => comment.mutate()}
          >
            {comment.isPending ? t("appeals.sendingComment") : t("appeals.sendComment")}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
