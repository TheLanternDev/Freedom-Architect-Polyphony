import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface SectionDividerProps {
  label: ReactNode;
  className?: string;
  monoSuffix?: ReactNode;
}

/** Etykieta sekcji z linią — spójny separator w całym workspace. */
export function SectionDivider({
  label,
  className,
  monoSuffix,
}: SectionDividerProps) {
  return (
    <div className={cn("aw-section-divider", className)}>
      <span className="aw-eyebrow text-text-tertiary shrink-0">{label}</span>
      <div className="aw-section-divider-line" aria-hidden />
      {monoSuffix != null && (
        <span className="font-mono text-[10px] text-text-tertiary/70 shrink-0">
          {monoSuffix}
        </span>
      )}
    </div>
  );
}
