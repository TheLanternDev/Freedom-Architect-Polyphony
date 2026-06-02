import { useState, type ReactNode } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";

interface SidebarSectionProps {
  label: string;
  children: ReactNode;
  className?: string;
  collapsible?: boolean;
  defaultOpen?: boolean;
  badge?: number;
  badgeUrgent?: boolean;
  disabled?: boolean;
  onOpenChange?: (open: boolean) => void;
}

/** Sidebar block — section label + optional collapsible content. */
export function SidebarSection({
  label,
  children,
  className,
  collapsible = false,
  defaultOpen = false,
  badge,
  badgeUrgent = false,
  disabled = false,
  onOpenChange,
}: SidebarSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const reduceMotion = useReducedMotion();

  const toggle = () => {
    if (disabled) return;
    setOpen((v) => {
      const next = !v;
      onOpenChange?.(next);
      return next;
    });
  };

  if (!collapsible) {
    return (
      <section className={cn("space-y-2", className)}>
        <p className="aw-eyebrow px-1 text-text-tertiary">{label}</p>
        {children}
      </section>
    );
  }

  return (
    <section className={cn("space-y-2", className)}>
      <button
        type="button"
        onClick={toggle}
        disabled={disabled}
        className={cn(
          "group flex w-full items-center justify-between px-1 py-1 rounded-control transition-colors duration-premium hover:text-text-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1",
          disabled && "opacity-40 cursor-not-allowed",
        )}
        style={{ outlineColor: "var(--aw-accent-border)" }}
      >
        <span className="flex items-center gap-2 min-w-0">
          <span className="aw-eyebrow text-text-tertiary group-hover:text-text-secondary transition-colors">
            {label}
          </span>
          {badge != null && badge > 0 && (
            <span
              className={cn(
                "inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full text-[9px] font-semibold tabular-nums",
                badgeUrgent
                  ? "bg-red-500/80 text-white"
                  : "bg-teal-dim text-teal-light border border-teal/25",
              )}
            >
              {badge}
            </span>
          )}
        </span>
        <Icon
          icon={ChevronDown}
          size="sm"
          className={cn(
            "text-text-tertiary transition-transform duration-premium",
            open && "rotate-180",
          )}
        />
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="content"
            initial={reduceMotion ? { opacity: 1, height: "auto" } : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
