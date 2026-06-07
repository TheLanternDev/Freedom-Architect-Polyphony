import { useMemo, useState } from "react";
import type { AxisPole, TensionAxisPayload, TensionNode } from "@/types/debate";

/**
 * TensionAxis — hierarchiczna wizualizacja napięć (Zadanie 1).
 *
 * Zamiast spłaszczonego Mermaida: pionowa OŚ CENTRALNA (rdzeń u góry, świetlny
 * kręgosłup) z węzłami napięć rozwieszonymi wokół niej. Kodowanie:
 *  • Y  = depth (hierarchia): powierzchnia przy rdzeniu → korzeń niżej.
 *  • X  = axis_pole: structural=lewo, somatic=centrum (przy osi), shadow=prawo.
 *  • rozmiar + kolor węzła = intensity.
 *  • kropki agentów = polifonia (tożsamość głosów Rady) bez niszczenia hierarchii.
 * Interakcja: hover/click węzła → podświetlenie + onFocusAnchor(proza);
 * hover agenta → nitka polifonii (podświetla wszystkie węzły z tym głosem).
 *
 * Paleta: złoto/teal/bursztyn/czerwień (design system) — bez UI-blue. Niebieski
 * dopuszczony WYŁĄCZNIE jako kolor tożsamości agentów (Obver/Relacjan), nie chrome.
 */

const POLE_X: Record<AxisPole, number> = {
  structural: 24,
  somatic: 50,
  shadow: 76,
};
const POLE_LABEL: Record<AxisPole, string> = {
  structural: "strukturalne",
  somatic: "somatyczne",
  shadow: "cień",
};

// Kolory tożsamości agentów — zgodne 1:1 ze stroke z CouncilCircle (spójność
// między widokami). Globalne dopasowanie do kanonu emoji 🟢🌱🔷🟡🟤 = osobna
// propozycja do akceptacji (mapping jest święty).
const AGENT_COLOR: Record<string, string> = {
  Kogit: "#818cf8",
  Szow: "#a1a1aa",
  Kidi: "#f472b6",
  Tai: "#fbbf24",
  Obver: "#34d399",
  Relacjan: "#60a5fa",
  Emojy: "#fb7185",
  Smaty: "#a8a29e",
  Deega: "#f87171",
  Syez: "#C5A46E",
};

function intensityColor(i: number): string {
  if (i >= 0.72) return "#E0584F"; // wysoka — przygaszona czerwień
  if (i >= 0.45) return "#D9A441"; // średnia — bursztyn
  return "#6FA8A8"; // niska — teal
}

interface PlacedNode extends TensionNode {
  idx: number;
  x: number;
  y: number;
  r: number;
}

interface Props {
  axis: TensionAxisPayload;
  /** Podświetlenie fragmentu prozy odpowiadającego napięciu. */
  onFocusAnchor?: (anchor: string) => void;
}

export function TensionAxis({ axis, onFocusAnchor }: Props) {
  const [active, setActive] = useState<number | null>(null);
  const [pinned, setPinned] = useState<number | null>(null);
  const [hoverAgent, setHoverAgent] = useState<string | null>(null);

  const FIRST_Y = 16;
  const ROW = 15;

  const { nodes, height } = useMemo(() => {
    const sorted = [...(axis.tensions ?? [])].sort(
      (a, b) => (a.depth ?? 1) - (b.depth ?? 1) || b.intensity - a.intensity,
    );
    const placed: PlacedNode[] = sorted.map((tn, i) => ({
      ...tn,
      idx: i,
      x: POLE_X[tn.axis_pole] ?? 50,
      y: FIRST_Y + i * ROW,
      r: 2.6 + Math.max(0, Math.min(1, tn.intensity)) * 3.6,
    }));
    const h = FIRST_Y + Math.max(1, placed.length) * ROW + 4;
    return { nodes: placed, height: h };
  }, [axis.tensions]);

  const focus = pinned ?? active;
  const tip = focus != null ? nodes.find((n) => n.idx === focus) : null;

  const isDim = (n: PlacedNode): boolean => {
    if (hoverAgent) return !n.between.includes(hoverAgent);
    if (focus != null) return n.idx !== focus;
    return false;
  };

  const onEnter = (n: PlacedNode) => {
    setActive(n.idx);
    if (n.prose_anchor && onFocusAnchor) onFocusAnchor(n.prose_anchor);
  };

  return (
    <section className="my-4 rounded-xl border border-gold/20 bg-black/30 px-4 py-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-[11px] uppercase tracking-widest text-gold/60">
          Oś napięć — hierarchia Rady
        </h3>
        <span className="text-[9px] text-white/30">structural ↔ somatic ↔ cień</span>
      </div>

      {/* RDZEŃ — centralna oś wyciągnięta z prozy */}
      <div className="relative mx-auto max-w-xl text-center mb-1">
        <div className="text-[13px] leading-none text-gold/70 mb-1 select-none">☼</div>
        <div className="inline-block rounded-lg border border-gold/40 bg-gold/[0.08] px-4 py-2 shadow-[0_0_24px_rgba(197,164,110,0.18)]">
          <div className="text-[9px] uppercase tracking-widest text-gold/50 mb-0.5">
            Rdzeń
          </div>
          <p className="font-serif text-[14px] leading-snug text-[#E8D5A3]">
            {axis.central_axis?.core}
          </p>
        </div>
      </div>

      <div className="relative mx-auto max-w-xl">
        <svg
          viewBox={`0 0 100 ${height}`}
          className="w-full select-none"
          style={{ overflow: "visible" }}
        >
          <defs>
            <linearGradient id="ta-spine" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#C5A46E" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#3D8B8B" stopOpacity="0.35" />
            </linearGradient>
          </defs>

          {/* Kręgosłup — oś centralna */}
          <line
            x1="50"
            y1="2"
            x2="50"
            y2={height - 2}
            stroke="url(#ta-spine)"
            strokeWidth="1.4"
            strokeLinecap="round"
          />

          {/* Łączniki węzeł → oś (grubość = intensity) */}
          {nodes.map((n) => (
            <line
              key={`c-${n.idx}`}
              x1="50"
              y1={n.y}
              x2={n.x}
              y2={n.y}
              stroke={intensityColor(n.intensity)}
              strokeWidth={0.4 + n.intensity * 1.6}
              strokeLinecap="round"
              style={{ opacity: isDim(n) ? 0.18 : 0.85, transition: "opacity 200ms" }}
            />
          ))}

          {/* Węzły napięć */}
          {nodes.map((n) => {
            const col = intensityColor(n.intensity);
            const dim = isDim(n);
            return (
              <g
                key={`n-${n.idx}`}
                style={{ opacity: dim ? 0.22 : 1, transition: "opacity 200ms", cursor: "pointer" }}
                onMouseEnter={() => onEnter(n)}
                onMouseLeave={() => setActive(null)}
                onClick={() => setPinned((p) => (p === n.idx ? null : n.idx))}
              >
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={n.r}
                  fill={col}
                  fillOpacity={0.18}
                  stroke={col}
                  strokeWidth={focus === n.idx ? 1.1 : 0.7}
                />
                {/* Kropki tożsamości agentów (polifonia) */}
                {n.between.slice(0, 2).map((ag, k) => (
                  <circle
                    key={ag + k}
                    cx={n.x + (k === 0 ? -n.r - 1.6 : n.r + 1.6)}
                    cy={n.y}
                    r={1.3}
                    fill={AGENT_COLOR[ag] ?? "#cbd5e1"}
                    stroke="#0A0D14"
                    strokeWidth={0.3}
                    style={{ cursor: "pointer" }}
                    onMouseEnter={(e) => {
                      e.stopPropagation();
                      setHoverAgent(ag);
                    }}
                    onMouseLeave={(e) => {
                      e.stopPropagation();
                      setHoverAgent(null);
                    }}
                  >
                    <title>{ag}</title>
                  </circle>
                ))}
              </g>
            );
          })}
        </svg>
      </div>

      {/* Tooltip / szczegół aktywnego napięcia */}
      <div className="mt-3 min-h-[44px]">
        {tip ? (
          <div className="rounded-lg border border-white/10 bg-black/40 px-3 py-2">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {tip.between.map((ag) => (
                <span
                  key={ag}
                  className="inline-flex items-center gap-1 text-[11px] text-white/75"
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ background: AGENT_COLOR[ag] ?? "#cbd5e1" }}
                  />
                  {ag}
                </span>
              ))}
              <span className="text-[9px] uppercase tracking-wider text-white/35">
                · {POLE_LABEL[tip.axis_pole]} · {tip.intensity.toFixed(2)}
              </span>
            </div>
            {tip.why && (
              <p className="text-[12px] leading-snug text-white/70">{tip.why}</p>
            )}
          </div>
        ) : (
          <p className="text-[11px] text-white/30 italic">
            Najedź na węzeł, by zobaczyć napięcie. Najedź na kropkę agenta, by
            prześledzić jego nitkę przez całą strukturę.
          </p>
        )}
      </div>

      {/* Legenda intensywności */}
      <div className="mt-3 flex flex-wrap gap-3 text-[9px] text-white/40">
        <span className="inline-flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ background: "#E0584F" }} /> wysokie
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ background: "#D9A441" }} /> średnie
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-2 h-2 rounded-full" style={{ background: "#6FA8A8" }} /> niskie
        </span>
      </div>
    </section>
  );
}
