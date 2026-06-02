import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface FadeInProps {
  children: ReactNode;
  className?: string;
  /** Opóźnienie wejścia (s) — do delikatnego staggeru sekcji. */
  delay?: number;
  /** Przesunięcie Y w px przy wejściu. */
  y?: number;
}

/** Spokojne wejście sekcji — respektuje prefers-reduced-motion. */
export function FadeIn({ children, className, delay = 0, y = 10 }: FadeInProps) {
  const reduceMotion = useReducedMotion();

  if (reduceMotion) {
    return <div className={className}>{children}</div>;
  }

  return (
    <motion.div
      className={cn(className)}
      initial={{ opacity: 0, y }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.38,
        delay,
        ease: [0.25, 0.1, 0.25, 1],
      }}
    >
      {children}
    </motion.div>
  );
}
