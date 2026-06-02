import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type CardVariant = "default" | "elevated" | "flat";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  padding?: "none" | "sm" | "md" | "lg";
}

const VARIANT_CLASS: Record<CardVariant, string> = {
  default: "aw-card",
  elevated: "aw-surface rounded-card shadow-elevated",
  flat: "bg-surface rounded-card border border-border",
};

const PADDING_CLASS: Record<NonNullable<CardProps["padding"]>, string> = {
  none: "p-0",
  sm: "p-4",
  md: "p-6",
  lg: "p-8",
};

/** Premium surface card — base primitive for panels and content blocks. */
export function Card({
  variant = "default",
  padding,
  className,
  children,
  ...props
}: CardProps) {
  const pad = padding ?? (variant === "default" ? undefined : "md");
  return (
    <div
      className={cn(
        VARIANT_CLASS[variant],
        pad && PADDING_CLASS[pad],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}
