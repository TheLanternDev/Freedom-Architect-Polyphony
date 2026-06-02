import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

type IconSize = "sm" | "md" | "lg";

const SIZE_CLASS: Record<IconSize, string> = {
  sm: "aw-icon-sm",
  md: "aw-icon-md",
  lg: "aw-icon-lg",
};

interface IconProps {
  icon: LucideIcon;
  size?: IconSize;
  className?: string;
  "aria-hidden"?: boolean;
}

/** Consistent Lucide icon wrapper — use across the app instead of raw SVGs. */
export function Icon({
  icon: LucideComponent,
  size = "md",
  className,
  "aria-hidden": ariaHidden = true,
}: IconProps) {
  return (
    <LucideComponent
      className={cn(SIZE_CLASS[size], className)}
      aria-hidden={ariaHidden}
    />
  );
}
