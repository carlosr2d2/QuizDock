import { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export const surfaceClass = "rounded-xl border border-border bg-card shadow-sm";

export const surfaceListClass = `${surfaceClass} divide-y divide-border overflow-hidden`;

export const nestedListClass = "divide-y divide-border overflow-hidden rounded-xl border border-border";

export const listItemClass = "px-5 py-4";

export const listRowHoverClass =
  "transition-colors duration-200 hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset";

export const listRowSelectedClass = "bg-accent/10";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn(surfaceClass, "p-6", className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn("text-base font-semibold tracking-tight", className)} {...props} />;
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("mt-1 text-sm text-muted-foreground", className)} {...props} />;
}
