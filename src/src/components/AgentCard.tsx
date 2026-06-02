import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLang } from "@/lib/i18n";
import type { AgentState } from "@/types/debate";

/**
 * Stage 3 / Premium redesign:
 * - Ujednolicony ciemny background dla wszystkich kart (koniec z tęczą 9 kolorów)
 * - Tożsamość agenta niesie avatar chip — jeden kolor per archetype, desaturowany
 * - Stany: idle=opacity-40, speaking=gold border glow, done=teal accent
 * - Wskaźnik mówienia: złoty pulsujący dot zamiast emoji 🎤 + bounce dots
 * - Tokeny design-systemu zamiast hardcoded `text-white/*`
 *
 * Bezpieczeństwo: agent.text renderowany jako text node (nie innerHTML),
 * brak nowych powierzchni ataku. Dane są tenant-isolated na backendzie.
 */

/** Jedna nasycona barwa avatara per archetype — wszystkie są ciemne, desaturowane. */
const AGENT_META: Record<string, { avatarBg: string; avatarText: string; initials: string }> = {
  Relacjan: { avatarBg: "bg-blue-950/80 border-blue-600/30",    avatarText: "text-blue-300/90",    initials: "RE" },
  Kogit:    { avatarBg: "bg-indigo-950/80 border-indigo-600/30", avatarText: "text-indigo-300/90",  initials: "KO" },
  Emojy:    { avatarBg: "bg-rose-950/70 border-rose-600/25",     avatarText: "text-rose-300/90",    initials: "EM" },
  Deega:    { avatarBg: "bg-red-950/80 border-red-700/30",       avatarText: "text-red-400/90",     initials: "DE" },
  Smaty:    { avatarBg: "bg-stone-900/80 border-stone-600/25",   avatarText: "text-stone-300/90",   initials: "SM" },
  Szow:     { avatarBg: "bg-zinc-900/90 border-zinc-600/20",     avatarText: "text-zinc-400/90",    initials: "SZ" },
  Tai:      { avatarBg: "bg-amber-950/70 border-amber-700/25",   avatarText: "text-amber-300/90",   initials: "TA" },
  Obver:    { avatarBg: "bg-emerald-950/70 border-emerald-700/25",avatarText: "text-emerald-400/90",initials: "OB" },
  Kidi:     { avatarBg: "bg-pink-950/60 border-pink-600/25",     avatarText: "text-pink-300/90",    initials: "KI" },
};

interface Props {
  agent: AgentState;
}

export function AgentCard({ agent }: Props) {
  const { t } = useLang();
  const meta = AGENT_META[agent.name] ?? {
    avatarBg: "bg-surface border-border",
    avatarText: "text-text-tertiary",
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
        boxShadow: isSpeaking
          ? "0 0 0 1px rgba(197,164,110,0.35), 0 4px 24px rgba(197,164,110,0.08)"
          : isDone
          ? "0 0 0 1px rgba(61,139,139,0.20)"
          : "0 0 0 1px rgba(30,36,51,1)",
      }}
      transition={{ duration: 0.22, ease: "easeOut" }}
      className={[
        "relative rounded-xl border p-4 min-h-[140px] transition-colors duration-220",
        "bg-surface-raised/60",
        isDone   ? "border-teal/20"          : "",
        isSpeaking ? "border-gold/30"        : "",
        (!isDone && !isSpeaking) ? "border-border" : "",
        agent.status === "idle" ? "opacity-40" : "",
      ].join(" ")}
    >
      {/* ── Header ── */}
      <div className="flex items-center gap-2.5 mb-2.5">
        {/* Avatar chip — única cor per agente */}
        <div className={[
          "w-7 h-7 rounded-lg border flex items-center justify-center",
          "text-[10px] font-semibold tracking-wide flex-shrink-0",
          meta.avatarBg, meta.avatarText,
        ].join(" ")}>
          {meta.initials}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <span className="text-[13px] font-medium text-text-primary leading-tight">
              {agent.name}
            </span>
            {hasBio && (
              <button
                type="button"
                onClick={() => setShowBio((v) => !v)}
                className="text-[9px] text-text-tertiary/50 hover:text-teal/70 transition-colors leading-none px-0.5"
                title="Kim jest?"
                aria-label={`Opis agenta ${agent.name}`}
              >
                {showBio ? "▲" : "?"}
              </button>
            )}
          </div>
          <div className="text-[10px] text-text-tertiary leading-tight truncate mt-0.5">
            {role}
          </div>
        </div>

        {/* Status indicator */}
        <div className="ml-auto flex-shrink-0 flex items-center gap-2">
          <AnimatePresence mode="wait">
            {(isAnalyzing || isSpeaking) && (
              <motion.span
                key="active"
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.8 }}
                transition={{ duration: 0.15 }}
                title={isAnalyzing ? t("agent.analyzing") : t("agent.speaking")}
              >
                {/* Gold pulse dot — zamiast emoji + bounce */}
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-gold opacity-50" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-gold/80" />
                </span>
              </motion.span>
            )}
          </AnimatePresence>
          {isDone && (
            <motion.span
              initial={{ opacity: 0, scale: 0.6 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: "spring", stiffness: 500, damping: 30 }}
              className="text-teal text-[11px] font-medium"
              aria-label="Ukończone"
            >
              ✓
            </motion.span>
          )}
        </div>
      </div>

      {/* ── Progress bar ── */}
      {(isAnalyzing || isSpeaking || isDone) && (
        <div className="mb-2.5 h-[2px] rounded-full bg-border overflow-hidden">
          <div
            className={[
              "h-full rounded-full transition-all duration-500",
              isDone ? "bg-teal/60" : isSpeaking ? "bg-gold/60" : "bg-border",
            ].join(" ")}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}

      {/* ── Bio (rozwijany) ── */}
      {showBio && hasBio && (
        <div className="mb-2.5 text-[11px] text-text-tertiary leading-relaxed italic border-l border-teal/30 pl-2.5">
          {bio}
        </div>
      )}

      {/* ── Treść głosu ── */}
      <div className={[
        "text-[12.5px] text-text-secondary leading-relaxed",
        deep ? "" : "line-clamp-4",
      ].join(" ")}>
        {agent.status === "idle" && (
          <span className="text-text-tertiary/40 italic">{t("agent.waiting")}</span>
        )}
        {(isAnalyzing || isSpeaking || isDone) && (
          <>
            {deep ? agent.text : preview}
            {isSpeaking && (
              <span className="inline-block w-[1.5px] h-[12px] bg-gold/70 ml-[2px] align-text-bottom animate-pulse" />
            )}
          </>
        )}
      </div>

      {/* ── Rozwinięcie głosu ── */}
      {(isSpeaking || isDone) && agent.text.length > 120 && (
        <button
          type="button"
          onClick={() => setDeep((v) => !v)}
          className="mt-3 text-[11px] text-teal/80 hover:text-teal-light transition-colors underline-offset-2 hover:underline"
        >
          {deep ? t("agent.collapse") : t("agent.go_deeper")}
        </button>
      )}
    </motion.div>
  );
}
