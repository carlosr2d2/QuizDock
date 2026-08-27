"use client";

import { useEffect, useState } from "react";

import { fetchCover } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

type DocumentCoverProps = {
  documentId?: string | null;
  hasCover?: boolean;
  kind?: string | null;
  title?: string | null;
  className?: string;
};

export function documentKindLabel(kind: string | null | undefined, fileLabel: string): string {
  switch (kind) {
    case "pdf":
      return "PDF";
    case "txt":
      return "TXT";
    case "md":
      return "MD";
    case "docx":
    case "doc":
      return "Word";
    default:
      return fileLabel;
  }
}

export function DocumentCover({
  documentId,
  hasCover = true,
  kind,
  title,
  className,
}: DocumentCoverProps) {
  const t = useT();
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(documentId));

  useEffect(() => {
    if (!documentId) {
      setSrc(null);
      setLoading(false);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);
    setSrc(null);
    void fetchCover(documentId)
      .then((blob) => {
        if (cancelled) return;
        if (!blob) {
          setLoading(false);
          return;
        }
        objectUrl = URL.createObjectURL(blob);
        setSrc(objectUrl);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) {
          setSrc(null);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId, hasCover]);

  if (src) {
    return (
      <img
        src={src}
        alt={title ? t("documents.coverOf", { title }) : t("documents.cover")}
        className={cn(
          "h-[5.5rem] w-[4.1rem] shrink-0 rounded-md object-cover shadow-sm ring-1 ring-border",
          className,
        )}
      />
    );
  }

  const label = documentKindLabel(kind, t("documents.file"));
  return (
    <div
      className={cn(
        "relative flex h-[5.5rem] w-[4.1rem] shrink-0 flex-col items-center justify-center overflow-hidden rounded-md",
        "bg-gradient-to-br from-zinc-100 via-zinc-50 to-zinc-200 text-zinc-500",
        "ring-1 ring-border dark:from-zinc-800 dark:via-zinc-900 dark:to-zinc-950 dark:text-zinc-400",
        loading && "animate-pulse",
        className,
      )}
      aria-label={loading ? t("documents.loadingCover") : t("documents.documentKind", { label })}
      aria-busy={loading || undefined}
    >
      <span className="absolute inset-x-0 top-0 h-0.5 bg-accent" />
      {loading ? (
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-300 border-t-accent" />
      ) : (
        <>
          <svg
            viewBox="0 0 24 24"
            className="h-6 w-6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden="true"
          >
            <path d="M7 3.75h7.5L19.5 9v11.25A1.5 1.5 0 0 1 18 21.75H7A1.5 1.5 0 0 1 5.5 20.25V5.25A1.5 1.5 0 0 1 7 3.75Z" />
            <path d="M14.5 3.75V9H19.5" />
          </svg>
          <span className="mt-1 text-[10px] font-semibold tracking-[0.16em] uppercase">{label}</span>
        </>
      )}
    </div>
  );
}
