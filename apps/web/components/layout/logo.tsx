import { cn } from "@/lib/utils";

export function Logo({ className, inverted = false }: { className?: string; inverted?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 font-semibold tracking-tight",
        inverted && "text-sidebar-foreground",
        className,
      )}
    >
      <span className="flex h-7 w-7 items-center justify-center rounded-md bg-accent text-xs font-bold text-accent-foreground">
        Q
      </span>
      QuizDock
    </span>
  );
}
