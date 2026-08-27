"use client";

import { ErrorState } from "@/components/ui/error-state";
import { useT } from "@/lib/i18n/provider";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const t = useT();
  return (
    <div className="py-8">
      <ErrorState title={t("error.screen")} error={error} onRetry={reset} />
    </div>
  );
}
