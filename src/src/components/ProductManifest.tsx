import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ChevronDown, Info } from "lucide-react";
import { useLang } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";

export function ProductManifest() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  const reduceMotion = useReducedMotion();

  const points = t("manifest.body")
    .split("\n\n")
    .filter(Boolean);

  return (
    <section className="rounded-card border border-border/80 bg-surface-raised/30 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="group flex w-full items-start gap-3 text-left px-5 py-4 transition-colors duration-premium hover:bg-white/[0.02] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] rounded-card"
        style={{ outlineColor: "var(--aw-accent-border)" }}
      >
        <span className="flex items-center justify-center w-8 h-8 rounded-surface shrink-0 border border-border bg-surface text-text-tertiary group-hover:text-[var(--aw-accent-light)] group-hover:border-[var(--aw-accent-border)] transition-colors duration-premium mt-0.5">
          <Icon icon={Info} size="sm" />
        </span>
        <span className="flex-1 min-w-0">
          <span className="block text-[13px] font-medium text-text-secondary group-hover:text-text-primary transition-colors">
            {t("manifest.title")}
          </span>
          {!open && (
            <span className="block text-[12px] text-text-tertiary mt-1 leading-relaxed line-clamp-1">
              {points[0]}
            </span>
          )}
        </span>
        <Icon
          icon={ChevronDown}
          size="sm"
          className={cn(
            "text-text-tertiary mt-1 transition-transform duration-premium shrink-0",
            open && "rotate-180",
          )}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="body"
            initial={reduceMotion ? { opacity: 1, height: "auto" } : { height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={reduceMotion ? { opacity: 0 } : { height: 0, opacity: 0 }}
            transition={{ duration: 0.28, ease: [0.4, 0, 0.2, 1] }}
            className="overflow-hidden"
          >
            <div className="px-5 pb-5 pt-0 border-t border-border/60">
              <ul className="mt-4 space-y-3">
                {points.map((point, i) => (
                  <motion.li
                    key={i}
                    initial={reduceMotion ? { opacity: 1, x: 0 } : { opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: reduceMotion ? 0 : i * 0.04, duration: 0.25 }}
                    className="flex gap-3 text-[13px] text-text-secondary leading-relaxed"
                  >
                    <span
                      className="w-1 h-1 rounded-full shrink-0 mt-2"
                      style={{ backgroundColor: "var(--aw-accent)" }}
                    />
                    <span>{point}</span>
                  </motion.li>
                ))}
              </ul>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
