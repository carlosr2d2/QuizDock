"use client";

import { ErrorState } from "@/components/ui/error-state";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="py-8">
      <ErrorState title="Algo salió mal en esta pantalla" error={error} onRetry={reset} />
    </div>
  );
}
