import { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  description,
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement> & { title: string; description: string }) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-accent/30 bg-accent/10 px-6 py-16 text-center",
        className,
      )}
      {...props}
    >
      <h3 className="text-base font-medium">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-muted-foreground">{description}</p>
      {children ? <div className="mt-6">{children}</div> : null}
    </div>
  );
}
