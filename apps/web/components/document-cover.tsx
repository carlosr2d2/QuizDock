"use client";

import { useEffect, useState } from "react";

import { FadeImage } from "@/components/ui/fade-image";
import { fetchCover } from "@/lib/api";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

export type CoverSize = "sm" | "md";

const COVER_BOX: Record<CoverSize, string> = {
  sm: "h-[5.5rem] w-[4.1rem]",
  md: "h-24 w-[4.5rem]",
};

const COVER_SPINNER: Record<CoverSize, string> = {
  sm: "h-5 w-5",
  md: "h-6 w-6",
};

type DocumentCoverProps = {
  documentId?: string | null;
  hasCover?: boolean;
  kind?: string | null;
  title?: string | null;
  size?: CoverSize;
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

export function CoverSpinner({ size = "sm", className }: { size?: CoverSize; className?: string }) {
  return (
    <span
      className={cn(
        "animate-spin rounded-full border-2 border-zinc-300 border-t-accent dark:border-zinc-600 dark:border-t-accent",
        COVER_SPINNER[size],
        className,
      )}
    />
  );
}

export function CoverPlaceholder({
  loading = false,
  kind,
  size = "sm",
  className,
}: {
  loading?: boolean;
  kind?: string | null;
  size?: CoverSize;
  className?: string;
}) {
  const t = useT();
  const label = documentKindLabel(kind, t("documents.file"));
  return (
    <div
      className={cn(
        "relative flex shrink-0 flex-col items-center justify-center overflow-hidden rounded-md shadow-sm ring-1 ring-border",
        COVER_BOX[size],
        className,
      )}
      aria-label={loading ? t("documents.loadingCover") : t("documents.documentKind", { label })}
      aria-busy={loading || undefined}
    >
      <CoverFallback loading={loading} label={label} size={size} />
    </div>
  );
}

function CoverFallback({
  loading,
  label,
  size,
  fading,
}: {
  loading: boolean;
  label: string;
  size: CoverSize;
  fading?: boolean;
}) {
  return (
    <div
      className={cn(
        "absolute inset-0 flex flex-col items-center justify-center transition-opacity duration-500 ease-out",
        "bg-gradient-to-br from-zinc-100 via-zinc-50 to-zinc-200 text-zinc-500",
        "dark:from-zinc-800 dark:via-zinc-900 dark:to-zinc-950 dark:text-zinc-400",
        loading && "animate-pulse",
        fading && "opacity-0",
      )}
    >
      <span className="absolute inset-x-0 top-0 h-0.5 bg-accent" />
      {loading ? (
        <CoverSpinner size={size} />
      ) : (
        <>
          <svg
            viewBox="0 0 24 24"
            className={size === "md" ? "h-7 w-7" : "h-6 w-6"}
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

export function DocumentCover({
  documentId,
  hasCover = true,
  kind,
  title,
  size = "sm",
  className,
}: DocumentCoverProps) {
  const t = useT();
  const [src, setSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(documentId && hasCover));
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    if (!documentId || !hasCover) {
      setSrc(null);
      setRevealed(false);
      setLoading(false);
      return;
    }
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);
    setRevealed(false);
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

  const label = documentKindLabel(kind, t("documents.file"));
  const showSpinner = loading || Boolean(src && !revealed);

  return (
    <div
      className={cn(
        "relative shrink-0 overflow-hidden rounded-md shadow-sm ring-1 ring-border",
        COVER_BOX[size],
        className,
      )}
    >
      <CoverFallback
        loading={showSpinner}
        label={label}
        size={size}
        fading={revealed}
      />
      {src ? (
        <FadeImage
          src={src}
          alt={title ? t("documents.coverOf", { title }) : t("documents.cover")}
          className="absolute inset-0 h-full w-full object-cover"
          onRevealed={() => {
            setRevealed(true);
            setLoading(false);
          }}
          onError={() => {
            setSrc(null);
            setRevealed(false);
            setLoading(false);
          }}
        />
      ) : null}
    </div>
  );
}
