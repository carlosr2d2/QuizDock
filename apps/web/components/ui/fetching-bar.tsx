"use client";

import { useIsFetching, useIsMutating } from "@tanstack/react-query";

export function FetchingBar() {
  const fetching = useIsFetching();
  const mutating = useIsMutating();
  if (!fetching && !mutating) return null;

  return (
    <div
      className="pointer-events-none absolute inset-x-0 top-0 z-20 h-0.5 overflow-hidden bg-accent/20"
      role="status"
      aria-live="polite"
      aria-label="Actualizando información"
    >
      <div className="h-full w-full animate-pulse bg-accent" />
    </div>
  );
}
