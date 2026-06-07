import { useMemo, useState } from "react";
import { useLang } from "@/lib/i18n";
import type { LiveTensionPair } from "@/types/debate";

function edgeStyle(intensity: number): { stroke: string; sw: number } {
  if (intensity >= 0.72) return { stroke: "rgba(248,113,113,0.85)", sw: 2.2 };
  if (intensity >= 0.45) return { stroke: "rgba(251,191,36,0.75)", sw: 1.6 };
  // Niskie napięcie: teal z design-systemu (#3D8B8B) — usunięty UI-blue (regresja D).
  return { stroke: "rgba(61,139,139,0.8)", sw: 1.2 };
}

export function TensionMeter({ pairs }: { pairs: LiveTensionPair[] }) {
  const { t } = useLang();
  const [tip, setTip] = useState<string | null>(null);

  const { agents, edges } = useMemo(() => {
    const seen = new Set<string>();
    const ag: string[] = [];
    for (const p of pairs) {
      if (!seen.has(p.a)) {
        seen.add(p.a);
        ag.push(p.a);
      }
      if (!seen.has(p.b)) {
        seen.add(p.b);
        ag.push(p.b);
      }
    }
    const pos = new Map<string, { x: number; y: number }>();
    const cx = 50;
    const cy = 50;
    const R = 34;
    ag.forEach((name, i) => {
      const ang = (2 * Math.PI * i) / Math.max(1, ag.length) - Math.PI / 2;
      pos.set(name, { x: cx + R * Math.cos(ang), y: cy + R * Math.sin(ang) });
    });
    const ed: Array<{
      key: string;
      x1: number;
      y1: number;
      x2: number;
      y2: number;
      intensity: number;
      label: string;
    }> = [];
    for (const p of pairs.slice(0, 18)) {
      const A = pos.get(p.a);
      const B = pos.get(p.b);
      if (!A || !B) continue;
      ed.push({
        key: `${p.a}-${p.b}-${p.intensity}`,
        x1: A.x,
        y1: A.y,
        x2: B.x,
        y2: B.y,
        intensity: p.intensity,
        label: `${p.a} ↔ ${p.b}`,
      });
    }
    return { agents: ag, edges: ed };
  }, [pairs]);

  if (!pairs.length) return null;

  return (
    <section className="rounded-xl border border-white/[0.08] bg-white/[0.02] px-4 py-4">
      <h2 className="text-[11px] uppercase tracking-widest text-white/35 mb-1">
        {t("tensionmeter.title")}
      </h2>
      <p className="text-[10px] text-white/35 mb-3 leading-snug">{t("tensionmeter.hint")}</p>

      <div className="relative w-full max-w-md mx-auto aspect-[5/4]">
        <svg viewBox="0 0 100 100" className="w-full h-full select-none">
          {edges.map((e) => {
            const st = edgeStyle(e.intensity);
            return (
              <line
                key={e.key}
                x1={e.x1}
                y1={e.y1}
                x2={e.x2}
                y2={e.y2}
                stroke={st.stroke}
                strokeWidth={st.sw}
                strokeLinecap="round"
                className="cursor-crosshair transition-opacity hover:opacity-100"
                style={{ opacity: 0.92 }}
                onMouseEnter={() =>
                  setTip(
                    `${e.label} · ${e.intensity.toFixed(2)} — ${
                      e.intensity >= 0.72
                        ? t("tensionmeter.why.high")
                        : e.intensity >= 0.45
                          ? t("tensionmeter.why.mid")
                          : t("tensionmeter.why.low")
                    }`,
                  )
                }
                onMouseLeave={() => setTip(null)}
              />
            );
          })}
          {agents.map((name) => {
            const ang =
              (2 * Math.PI * agents.indexOf(name)) / Math.max(1, agents.length) - Math.PI / 2;
            const x = 50 + 34 * Math.cos(ang);
            const y = 50 + 34 * Math.sin(ang);
            return (
              <text
                key={name}
                x={x}
                y={y}
                textAnchor="middle"
                dominantBaseline="middle"
                fill="rgba(255,255,255,0.72)"
                style={{ fontSize: "4.2px" }}
                className="font-sans pointer-events-none"
              >
                {name.slice(0, 3)}
              </text>
            );
          })}
        </svg>
      </div>

      {tip && (
        <p className="mt-2 text-[11px] text-white/70 leading-snug border border-white/10 rounded-lg px-3 py-2 bg-black/30">
          {tip}
        </p>
      )}

      <div className="mt-3 flex flex-wrap gap-3 text-[9px] text-white/40">
        <span className="inline-flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-red-400/80" /> {t("tensionmeter.legend.high")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-amber-400/80" /> {t("tensionmeter.legend.mid")}
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-2 h-2 rounded-full bg-teal/80" /> {t("tensionmeter.legend.low")}
        </span>
      </div>
    </section>
  );
}
