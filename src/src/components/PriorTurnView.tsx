import { useState } from "react";
import { AgentCard } from "@/components/AgentCard";
import { SyezPanel } from "@/components/SyezPanel";
import { FadeIn } from "@/components/ui/FadeIn";
import { SectionDivider } from "@/components/ui/SectionDivider";
import { useLang } from "@/lib/i18n";
import type { PriorTurn } from "@/types/debate";

interface Props {
  turn: PriorTurn;
  /** 1-based, do nagłówka „Tura #N". */
  index: number;
}

export function PriorTurnView({ turn, index }: Props) {
  const { t } = useLang();
  const [expanded, setExpanded] = useState(false);
  const agents = Object.values(turn.agents);
  const hasSynthesis = Boolean(turn.synthesis || turn.synthesisStructured);
  const promptPreview =
    turn.promptText.length > 160
      ? `${turn.promptText.slice(0, 160).trim()}…`
      : turn.promptText;

  return (
    <FadeIn delay={index * 0.06} className="space-y-3">
      <SectionDivider
        label={`${t("thread.prior_turn")} #${index + 1}`}
        monoSuffix={turn.debateId != null ? `#${turn.debateId}` : undefined}
      />

      <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] overflow-hidden">
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-white/[0.03] transition-colors"
          aria-expanded={expanded}
        >
          <span className="mt-0.5 text-teal/70 text-[11px] shrink-0 w-4">
            {expanded ? "▾" : "▸"}
          </span>
          <div className="min-w-0 flex-1 space-y-1">
            {turn.promptText ? (
              <p className="text-[13px] text-white/75 leading-snug line-clamp-2">
                {expanded ? turn.promptText : promptPreview}
              </p>
            ) : null}
            <p className="text-[11px] text-white/35">
              {t("thread.prior_summary")
                .replace("{n}", String(agents.length))
                .replace("{synthesis}", hasSynthesis ? t("thread.prior_has_synthesis") : "")}
            </p>
          </div>
          <span className="text-[11px] text-teal/60 shrink-0 pt-0.5">
            {expanded ? t("thread.collapse") : t("thread.expand")}
          </span>
        </button>

        {expanded && (
          <div className="border-t border-white/[0.06] px-4 pb-4 pt-3 space-y-5">
            {agents.length > 0 && (
              <div className="aw-grid-council">
                {agents.map((a) => (
                  <AgentCard key={a.name} agent={a} />
                ))}
              </div>
            )}
            {hasSynthesis && (
              <SyezPanel
                synthesis={turn.synthesis}
                synthesisStructured={turn.synthesisStructured}
                status="done"
                debateId={turn.debateId}
                debateCost={turn.debateCost}
                debateMode={turn.debateMode}
                sticky={false}
                readOnly
              />
            )}
          </div>
        )}
      </div>
    </FadeIn>
  );
}
