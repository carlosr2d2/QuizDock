"use client";

import { ImgHTMLAttributes, useEffect, useState } from "react";

import { cn } from "@/lib/utils";

type FadeImageProps = ImgHTMLAttributes<HTMLImageElement> & {
  onRevealed?: () => void;
};

export function FadeImage({ className, onLoad, onRevealed, src, alt, ...props }: FadeImageProps) {
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    setRevealed(false);
  }, [src]);

  return (
    <img
      {...props}
      src={src}
      alt={alt ?? ""}
      onLoad={(event) => {
        onLoad?.(event);
        requestAnimationFrame(() => {
          setRevealed(true);
          onRevealed?.();
        });
      }}
      className={cn(
        "transition-opacity duration-500 ease-out",
        revealed ? "opacity-100" : "opacity-0",
        className,
      )}
    />
  );
}
