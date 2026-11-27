"use client";

import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";
import type { DocumentChunkPreview } from "@/types/api";

type ChunkPickerProps = {
  chunks: DocumentChunkPreview[];
  value: string;
  onChange: (chunkId: string, chunk: DocumentChunkPreview | null) => void;
  loading?: boolean;
  className?: string;
};

export function ChunkPicker({ chunks, value, onChange, loading = false, className }: ChunkPickerProps) {
  const t = useT();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return chunks;
    return chunks.filter((item) => {
      const haystack = [
        item.content,
        item.chapter ?? "",
        item.section ?? "",
        item.page_start != null ? String(item.page_start) : "",
        item.page_end != null ? String(item.page_end) : "",
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(needle);
    });
  }, [chunks, query]);

  const selectedIndex = chunks.findIndex((item) => item.id === value);
  const selected = selectedIndex >= 0 ? chunks[selectedIndex] : null;
  const previous = selectedIndex > 0 ? chunks[selectedIndex - 1] : null;
  const next = selectedIndex >= 0 && selectedIndex < chunks.length - 1 ? chunks[selectedIndex + 1] : null;

  if (loading) {
    return <p className="text-xs text-muted-foreground">{t("appeals.loadingChunks")}</p>;
  }

  if (!chunks.length) {
    return <p className="text-xs text-muted-foreground">{t("appeals.noChunks")}</p>;
  }

  return (
    <div className={cn("space-y-2", className)}>
      <Input
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={t("appeals.searchChunks")}
        aria-label={t("appeals.searchChunks")}
      />
      <p className="text-xs text-muted-foreground">
        {query.trim()
          ? t("appeals.chunkMatches", { count: filtered.length, total: chunks.length })
          : t("appeals.chunkCount", { count: chunks.length })}
      </p>

      <div
        role="listbox"
        aria-label={t("appeals.pickChunk")}
        className="max-h-72 space-y-2 overflow-y-auto rounded-md border border-border bg-background p-2"
      >
        {filtered.length ? (
          filtered.map((item) => {
            const active = item.id === value;
            return (
              <button
                key={item.id}
                type="button"
                role="option"
                aria-selected={active}
                onClick={() => onChange(item.id, item)}
                className={cn(
                  "w-full rounded-md border px-3 py-2 text-left transition-colors",
                  active
                    ? "border-accent bg-accent/10"
                    : "border-transparent hover:border-border hover:bg-muted/60",
                )}
              >
                <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                  {formatChunkMeta(item, t)}
                </p>
                <p
                  className={cn(
                    "mt-1 whitespace-pre-wrap text-sm leading-snug text-foreground",
                    !active && "line-clamp-4",
                  )}
                >
                  {item.content}
                </p>
              </button>
            );
          })
        ) : (
          <p className="px-2 py-3 text-sm text-muted-foreground">{t("appeals.noChunkMatches")}</p>
        )}
      </div>

      {selected ? (
        <div className="rounded-md border border-accent/30 bg-accent/5 px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs font-medium text-foreground">{t("appeals.selectedChunk")}</p>
            <button
              type="button"
              className="text-xs text-muted-foreground underline-offset-4 hover:underline"
              onClick={() => onChange("", null)}
            >
              {t("appeals.clearChunk")}
            </button>
          </div>
          <p className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            {formatChunkMeta(selected, t)}
          </p>
          {previous ? (
            <div className="mt-2 rounded border border-border/60 bg-background/70 px-2 py-1.5">
              <p className="text-[11px] font-medium text-muted-foreground">{t("appeals.chunkPrevContext")}</p>
              <p className="mt-0.5 line-clamp-3 whitespace-pre-wrap text-xs leading-snug text-muted-foreground">
                {previous.content}
              </p>
            </div>
          ) : null}
          <p className="mt-2 whitespace-pre-wrap text-sm leading-snug text-foreground">{selected.content}</p>
          {next ? (
            <div className="mt-2 rounded border border-border/60 bg-background/70 px-2 py-1.5">
              <p className="text-[11px] font-medium text-muted-foreground">{t("appeals.chunkNextContext")}</p>
              <p className="mt-0.5 line-clamp-3 whitespace-pre-wrap text-xs leading-snug text-muted-foreground">
                {next.content}
              </p>
            </div>
          ) : null}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">{t("appeals.pickChunkHint")}</p>
      )}
    </div>
  );
}

function formatChunkMeta(
  item: DocumentChunkPreview,
  t: (key: string, vars?: Record<string, string | number>) => string,
): string {
  const parts: string[] = [];
  if (item.page_start != null) {
    parts.push(
      item.page_end != null && item.page_end !== item.page_start
        ? t("appeals.chunkPages", { start: item.page_start, end: item.page_end })
        : t("appeals.chunkPage", { page: item.page_start }),
    );
  }
  if (item.chapter?.trim()) {
    parts.push(t("appeals.chunkChapter", { chapter: item.chapter.trim() }));
  }
  if (item.section?.trim()) {
    parts.push(t("appeals.chunkSection", { section: item.section.trim() }));
  }
  if (!parts.length) {
    parts.push(t("appeals.chunkPosition", { position: item.position + 1 }));
  }
  return parts.join(" · ");
}
