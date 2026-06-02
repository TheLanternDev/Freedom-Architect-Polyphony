import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLang } from "@/lib/i18n";
import type { AgentState } from "@/types/debate";

const AGENT_META: Record<string, { color: string; initials: string }> = {
  Relacjan: { color: "bg-blue-900/40 border-blue-500/40", initials: "RE" },
  Kogit: { color: "bg-purple-900/40 border-purple-500/40", initials: "KO" },
  Emojy: { color: "bg-violet-900/40 border-violet-500/45", initials: "EM" },
  Deega: { color: "bg-red-900/40 border-red-500/40", initials: "DE" },
  Smaty: { color: "bg-amber-900/40 border-amber-700/40", initials: "SM" },
  Szow: { color: "bg-zinc-950/70 border-zinc-500/30", initials: "SZ" },
  Tai: { color: "bg-orange-900/40 border-orange-500/40", initials: "TA" },
  Obver: { color: "bg-green-900/40 border-green-500/40", initials: "OB" },
  Kidi: { color: "bg-fuchsia-950/40 border-fuchsia-500/40", initials: "KI" },
};

interface Props {
  agent: AgentState;
}

export function AgentCard({ agent }: Props) {
  const { t } = useLang();
  const meta = AGENT_META[agent.name] ?? {
    color: "bg-surface-raised border-border",
    initials: agent.name.slice(0, 2).toUpperCase(),
  };
  const roleKey = `agent.role.${agent.name}`;
  const role = AGENT_META[agent.name] ? t(roleKey) : t("agent.fallback_role");
  const bio = t(`agent.bio.${agent.name}`);
  const hasBio = bio !== `agent.bio.${agent.name}`;

  const [deep, setDeep] = useState(false);
  const [showBio, setShowBio] = useState(false);
  const isSpeaking = agent.status === "speaking";
  const isAnalyzing = agent.status === "analyzing";
  const isDone = agent.status === "done";

  const preview =
    agent.text.split(/(?<=[.!?])\s+/).slice(0, 3).join(" ").trim() ||
    agent.text.slice(0, 220);

  const pct = Math.max(0, Math.min(100, agent.progress ?? (isDone ? 100 : 0)));

  return (
    <motion.div
      initial={false}
      animate={{
        scale: isSpeaking ? 1.01 : 1,
        boxShadow: isSpeaking
          ? "0 0 20px rgba(251,191,36,0.14)"
          : "0 0 0 rgba(0,0,0,0)",
      }}
      transition={{ type: "spring", stiffness: 420, damping: 28 }}
      className={`
        relative rounded-xl border p-4 min-h-[140px]
        ${meta.color}
        ${isDone ? "ring-1 ring-teal-400/30 opacity-95" : ""}
        ${isSpeaking ? "ring-2 ring-amber-400/50" : ""}
        ${agent.status === "idle" ? "opacity-45 border-white/10" : ""}
      `}
    >
      <div className="flex items-center gap-2 mb-2">
        <div className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center text-[11px] font-medium text-white/80 flex-shrink-0">
          {meta.initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1">
            <div className="text-[13px] font-medium text-white leading-tight">{agent.name}</div>
            {hasBio && (
              <button
                type="button"
                onClick={() => setShowBio((v) => !v)}
                className="text-[9px] text-white/25 hover:text-teal/70 transition-colors leading-none"
                title="Kim jest?"
              >
                {showBio ? "▲" : "?"}
              </button>
            )}
          </div>
          <div className="text-[10px] text-white/40 leading-tight truncate">{role}</div>
        </div>

        <div className="ml-auto flex-shrink-0 flex items-center gap-2">
          <AnimatePresence mode="wait">
            {isAnalyzing && (
              <motion.span
                key="an"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex gap-1 items-center"
                title={t("agent.analyzing")}
              >
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal opacity-60" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-teal" />
                </span>
              </motion.span>
            )}
            {isSpeaking && !isAnalyzing && (
              <motion.span
                key="sp"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex gap-1 items-center text-amber-200/90"
                title={t("agent.speaking")}
              >
                <span className="text-[12px]" aria-hidden>
                  🎤
                </span>
                {[0, 1, 2].map((i) => (
                  <span
                    key={i}
                    className="w-[4px] h-[4px] rounded-full bg-amber-300 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </motion.span>
            )}
          </AnimatePresence>
          {isDone && (
            <span className="text-teal text-[11px]" aria-hidden>
              ✓
            </span>
          )}
        </div>
      </div>

      {(isAnalyzing || isSpeaking || isDone) && (
        <div className="mb-2 h-1 rounded-full bg-white/[0.08] overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-300 ${
              isDone ? "bg-teal" : isSpeaking ? "bg-amber-400/90" : "bg-white/25"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {showBio && hasBio && (
        <div className="mb-2 text-[11px] text-white/50 leading-relaxed italic border-l-2 border-teal/30 pl-2">
          {bio}
        </div>
      )}

      <div
        className={`text-[12px] text-white/70 leading-relaxed ${
          deep ? "" : "line-clamp-4"
        }`}
      >
        {agent.status === "idle" && (
          <span className="text-white/20 italic">{t("agent.waiting")}</span>
        )}
        {(isAnalyzing || isSpeaking || isDone) && (
          <>
            {deep ? agent.text : preview}
            {isSpeaking && (
              <span className="inline-block w-[2px] h-[12px] bg-amber-300 ml-[2px] align-text-bottom animate-pulse" />
            )}
          </>
        )}
      </div>

      {(isSpeaking || isDone) && agent.text.length > 120 && (
        <button
          type="button"
          onClick={() => setDeep((v) => !v)}
          className="mt-3 text-[11px] text-teal/90 hover:text-teal-light underline-offset-2 hover:underline"
        >
          {deep ? t("agent.collapse") : t("agent.go_deeper")}
        </button>
      )}
    </motion.div>
  );
}
