/**
 * CouncilCircle — Sala Rady (Krok 2 redesignu).
 *
 * Zastępuje grid AgentCard + TensionMeter gdy AW_COUNCIL_CIRCLE=1.
 * SVG: 9 agentów w kole + krawędzie napięć na żywo.
 * Panel detalu po prawej: pełny głos wybranego agenta.
 *
 * Bezpieczeństwo: tekst agenta renderowany jako text node, nie innerHTML.
 * Feature flag: localStorage.getItem("AW_COUNCIL_CIRCLE") === "1"
 */

import { useState } from "react";
import { useLang } from "@/lib/i18n";
import type { AgentState, LiveTensionPair } from "@/types/debate";

const CX = 150, CY = 150, R = 110;

const AGENT_ORDER = [
  "Kogit", "Szow", "Kidi", "Tai", "Obver", "Relacjan", "Emojy", "Smaty", "Deega",
];

const NODE_META: Record<string, { abbr: string; fill: string; stroke: string; text: string }> = {
  Kogit:    { abbr: "KO", fill: "#1e1b4b", stroke: "#818cf8", text: "#a5b4fc" },
  Szow:     { abbr: "SZ", fill: "#18181b", stroke: "#a1a1aa", text: "#d4d4d8" },
  Kidi:     { abbr: "KI", fill: "#4a0520", stroke: "#f472b6", text: "#f9a8d4" },
  Tai:      { abbr: "TA", fill: "#451a03", stroke: "#fbbf24", text: "#fcd34d" },
  Obver:    { abbr: "OB", fill: "#022c22", stroke: "#34d399", text: "#6ee7b7" },
  Relacjan: { abbr: "RE", fill: "#172554", stroke: "#60a5fa", text: "#93c5fd" },
  Emojy:    { abbr: "EM", fill: "#4c0519", stroke: "#fb7185", text: "#fda4af" },
  Smaty:    { abbr: "SM", fill: "#1c1917", stroke: "#a8a29e", text: "#d6d3d1" },
  Deega:    { abbr: "DE", fill: "#450a0a", stroke: "#f87171", text: "#fca5a5" },
};

function edgeColor(intensity: number): string {
  if (intensity >= 0.72) return "rgba(248,113,113,0.75)";
  if (intensity >= 0.45) return "rgba(251,191,36,0.65)";
  return "rgba(56,189,248,0.5)";
}

function nodePos(i: number, total: number): { x: number; y: number } {
  const angle = (2 * Math.PI * i / total) - Math.PI / 2;
  return {
    x: Math.round(CX + R * Math.cos(angle)),
    y: Math.round(CY + R * Math.sin(angle)),
  };
}

function nodeMeta(name: string) {
  return NODE_META[name] ?? {
    abbr: name.slice(0, 2).toUpperCase(),
    fill: "#0E1019",
    stroke: "#58627A",
    text: "#98A2B8",
  };
}

interface Props {
  agents: AgentState[];
  tensions: LiveTensionPair[];
}

export function CouncilCircle({ agents, tensions }: Props) {
  const { t } = useLang();
  const [selected, setSelected] = useState<string | null>(null);

  const agentMap = new Map(agents.map((a) => [a.name, a]));
  const orderedPresent = AGENT_ORDER.filter((n) => agentMap.has(n));

  const posMap = new Map(
    orderedPresent.map((name, i) => [name, nodePos(i, orderedPresent.length)])
  );

  const selectedAgent = selected ? agentMap.get(selected) : null;

  return (
    <div className="flex items-stretch min-h-[320px]">
      {/* ── Council circle ── */}
      <div className="flex-1 flex items-center justify-center py-4 min-w-0">
        <svg
          viewBox="0 0 300 300"
          className="w-full max-w-[300px]"
          aria-label="Sala Rady — koło agentów"
        >
          {/* Tension edges */}
          {tensions.slice(0, 16).map((p) => {
            const A = posMap.get(p.a), B = posMap.get(p.b);
            if (!A || !B) return null;
            return (
              <line
                key={`${p.a}-${p.b}`}
                x1={A.x} y1={A.y}
                x2={B.x} y2={B.y}
                stroke={edgeColor(p.intensity)}
                strokeWidth={p.intensity >= 0.72 ? 1.8 : p.intensity >= 0.45 ? 1.3 : 1}
                strokeLinecap="round"
              />
            );
          })}

          {/* Agent nodes */}
          {orderedPresent.map((name) => {
            const pos = posMap.get(name)!;
            const agent = agentMap.get(name)!;
            const meta = nodeMeta(name);
            const speaking = agent.status === "speaking" || agent.status === "analyzing";
            const done = agent.status === "done";
            const idle = agent.status === "idle";
            const isSelected = selected === name;

            const strokeColor = speaking ? "#C9A05A"
              : done ? "#3A8484"
              : isSelected ? "#ffffff"
              : idle ? "#232A3A"
              : meta.stroke;
            const strokeW = speaking || isSelected ? 2.2 : 1.5;
            const opacity = idle && !isSelected ? 0.4 : 1;

            return (
              <g
                key={name}
                onClick={() => setSelected(isSelected ? null : name)}
                style={{ cursor: "pointer", opacity }}
                role="button"
                aria-label={name}
                aria-pressed={isSelected}
              >
                {/* Speaking pulse ring */}
                {speaking && (
                  <circle cx={pos.x} cy={pos.y} r={14} fill="none" stroke="rgba(201,160,90,0.35)" strokeWidth={1}>
                    <animate attributeName="r" values="14;21;14" dur="1.6s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.6;0;0.6" dur="1.6s" repeatCount="indefinite" />
                  </circle>
                )}
                {/* Selection ring */}
                {isSelected && (
                  <circle cx={pos.x} cy={pos.y} r={18} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={1} />
                )}
                {/* Main circle */}
                <circle
                  cx={pos.x} cy={pos.y} r={13}
                  fill={meta.fill}
                  stroke={strokeColor}
                  strokeWidth={strokeW}
                />
                {/* Initials */}
                <text
                  x={pos.x} y={pos.y + 3}
                  textAnchor="middle"
                  fontSize={7}
                  fontFamily="Inter,sans-serif"
                  fontWeight="500"
                  fill={speaking ? "#C9A05A" : done ? "#3A8484" : meta.text}
                >
                  {meta.abbr}
                </text>
                {/* Short label under node */}
                <text
                  x={pos.x}
                  y={pos.y + (pos.y < CY ? -19 : 22)}
                  textAnchor="middle"
                  fontSize={5.5}
                  fontFamily="Inter,sans-serif"
                  fill={speaking ? "rgba(201,160,90,0.85)" : done ? "rgba(58,132,132,0.85)" : "rgba(152,162,184,0.55)"}
                >
                  {name.slice(0, 4)}
                </text>
              </g>
            );
          })}

          {/* Syez center hub */}
          <circle cx={CX} cy={CY} r={20} fill="#09090E" stroke="#1C2231" strokeWidth={1} />
          <text x={CX} y={CY - 3} textAnchor="middle" fontSize={6.5} fontFamily="Inter,sans-serif" fill="#58627A">
            SYEZ
          </text>
          <text x={CX} y={CY + 7} textAnchor="middle" fontSize={5} fontFamily="Inter,sans-serif" fill="#3A8484">
            słucha
          </text>
        </svg>
      </div>

      {/* ── Detail panel ── */}
      <div className="w-[220px] shrink-0 border-l border-border bg-[#09090F] flex flex-col overflow-hidden">
        {selectedAgent ? (
          <AgentDetail
            agent={selectedAgent}
            t={t}
            onClose={() => setSelected(null)}
          />
        ) : (
          <div className="flex-1 flex flex-col gap-4 px-4 py-5">
            <p className="text-[11px] text-text-tertiary leading-relaxed">
              {t("council_circle.select_hint") || "Kliknij agenta na kole, aby zobaczyć pełny głos."}
            </p>
            {tensions.length > 0 && (
              <TensionList tensions={tensions} />
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── AgentDetail ─────────────────────────────────────────────────── */

function AgentDetail({
  agent,
  t,
  onClose,
}: {
  agent: AgentState;
  t: (k: string) => string;
  onClose: () => void;
}) {
  const meta = nodeMeta(agent.name);
  const role = t(`agent.role.${agent.name}`);
  const speaking = agent.status === "speaking" || agent.status === "analyzing";
  const done = agent.status === "done";
  const pct = Math.max(0, Math.min(100, agent.progress ?? (done ? 100 : 0)));

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 px-4 pt-4 pb-3 border-b border-border flex items-center gap-2.5">
        <div
          className="w-7 h-7 rounded-lg border flex items-center justify-center text-[9px] font-semibold shrink-0"
          style={{ background: meta.fill, borderColor: speaking ? "#C9A05A" : done ? "#3A8484" : meta.stroke, color: speaking ? "#C9A05A" : done ? "#3A8484" : meta.text }}
        >
          {meta.abbr}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[12px] font-medium text-text-primary leading-tight">{agent.name}</p>
          <p className="text-[10px] text-text-tertiary truncate">{role}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-text-tertiary hover:text-text-secondary text-[14px] leading-none px-1"
          aria-label="Zamknij"
        >
          ×
        </button>
      </div>

      {/* Progress bar */}
      {(speaking || done) && (
        <div className="h-[2px] bg-border shrink-0">
          <div
            className="h-full transition-all duration-500"
            style={{
              width: `${pct}%`,
              background: speaking ? "#C9A05A" : "#3A8484",
              opacity: 0.7,
            }}
          />
        </div>
      )}

      {/* Voice text */}
      <div className="flex-1 overflow-y-auto px-4 py-3 aw-scroll">
        {agent.status === "idle" && (
          <p className="text-[11px] text-text-tertiary italic">
            {t("agent.waiting") || "Czeka na swoją kolej…"}
          </p>
        )}
        {(speaking || done) && (
          <p className="text-[12px] text-text-secondary leading-relaxed whitespace-pre-wrap">
            {agent.text}
            {speaking && (
              <span
                className="inline-block w-[1.5px] h-[11px] bg-gold/70 ml-[2px] align-text-bottom animate-pulse"
              />
            )}
          </p>
        )}
        {agent.status === "error" && (
          <p className="text-[11px] text-red-400/80 italic">
            {agent.text || t("agent.error") || "Błąd agenta."}
          </p>
        )}
      </div>
    </div>
  );
}

/* ── TensionList ─────────────────────────────────────────────────── */

function TensionList({ tensions }: { tensions: LiveTensionPair[] }) {
  const top = tensions.slice(0, 5);
  return (
    <div>
      <p className="text-[9px] uppercase tracking-widest text-text-tertiary/60 mb-2">
        Napięcia
      </p>
      <div className="space-y-2">
        {top.map((p) => (
          <div key={`${p.a}-${p.b}`}>
            <div className="flex justify-between text-[10px] mb-0.5">
              <span className="text-text-tertiary truncate">{p.a} ↔ {p.b}</span>
              <span style={{ color: edgeColor(p.intensity) }}>{p.intensity.toFixed(2)}</span>
            </div>
            <div className="h-[2px] bg-border/60 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${Math.round(p.intensity * 100)}%`,
                  background: edgeColor(p.intensity),
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
