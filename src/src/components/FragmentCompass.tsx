/**
 * AKSJOMAT 0 w UI — kompas Filozofii Fragmentu.
 *
 * To NIE jest todo. To kompas — stale widoczna mała ramka, która pokazuje
 * trzy elementy systemu (Uśmiech ↔ Perspektywa ↔ Droga) jako żywy, samopod-
 * trzymujący się układ. Klik w element rozwija krótki opis. Brak progresu,
 * brak procentów, brak "zaznacz jako zrobione" — bo to jest postawa, nie cel.
 */

import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";

type FragmentNode = "smile" | "perspective" | "path";

const NODES: Array<{
  key: FragmentNode;
  pl: string;
  icon: string;
  short: string;
  detail: string;
}> = [
  {
    key: "smile",
    pl: "Uśmiech",
    icon: "☺",
    short: "Postawa, nie emocja.",
    detail:
      'Ciekawość skierowana w siebie. „Ciekawe, jak sobie z tym poradzę" ' +
      '— nawet gdy trudno. Poszerza wewnętrzny horyzont, zmniejsza spinę. ' +
      'Nie wymaga że jest dobrze. Wymaga że jesteś.',
  },
  {
    key: "perspective",
    pl: "Perspektywa",
    icon: "◐",
    short: "Jak patrzeć, nie gdzie dojść.",
    detail:
      'Zmiana centrum z „cel" na „spojrzenie". Perspektywa nigdy się nie ' +
      'kończy — zawsze jest coś, czego jeszcze nie widziałeś. Karm ciekawość ' +
      'zamiast ją zabijać celem.',
  },
  {
    key: "path",
    pl: "Droga",
    icon: "↝",
    short: "Codzienne, rzeczywiste ruszanie się.",
    detail:
      "Bez Uśmiechu i Perspektywy Droga staje się pustostanem. Razem trzy " +
      "elementy tworzą układ, który podtrzymuje się sam — nawet gdy jeden " +
      "z nich słabnie.",
  },
];

export function FragmentCompass({ compact = false }: { compact?: boolean }) {
  const [active, setActive] = useState<FragmentNode | null>(null);
  const [expanded, setExpanded] = useState(!compact);
  const node = active ? NODES.find((n) => n.key === active) ?? null : null;

  return (
    <div
      className="rounded-card border border-border/80 bg-surface/95 backdrop-blur-md shadow-elevated"
      aria-label="Fragment — kompas (Uśmiech, Perspektywa, Droga)"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left hover:bg-white/[0.02] transition-colors rounded-card"
      >
        <span className="aw-eyebrow text-text-tertiary text-[9px]">
          Fragment · kompas
        </span>
        <span className="flex items-center gap-1.5 shrink-0">
          <span className="text-[9px] text-text-tertiary/70" title="AKSJOMAT 0">
            AKSJOMAT 0
          </span>
          <Icon
            icon={ChevronDown}
            size="sm"
            className={cn(
              "text-text-tertiary transition-transform duration-premium",
              expanded && "rotate-180",
            )}
          />
        </span>
      </button>

      {expanded && (
        <div className={cn("px-3 pb-3", compact ? "pt-0" : "pt-0")}>
          <div className="flex items-stretch gap-1.5">
            {NODES.map((n) => {
              const isActive = active === n.key;
              return (
                <button
                  key={n.key}
                  type="button"
                  onClick={() => setActive(isActive ? null : n.key)}
                  className={cn(
                    /* Stage 3: AKSJOMAT 0 używa gold (rdzeń filozofii), nie teal (teal = Syez/output) */
                    "flex-1 rounded-control border px-2 py-2 text-left transition-all duration-premium",
                    isActive
                      ? "border-gold/30 bg-gold-dim"
                      : "border-border bg-surface-raised/50 hover:border-gold/15 hover:bg-gold-dim/50",
                  )}
                  aria-pressed={isActive}
                >
                  <div className="text-base leading-none mb-1" aria-hidden>
                    {n.icon}
                  </div>
                  <div className="text-[11px] font-medium text-text-secondary">
                    {n.pl}
                  </div>
                  {!compact && (
                    <div className="text-[9px] text-text-tertiary mt-0.5 leading-snug">
                      {n.short}
                    </div>
                  )}
                </button>
              );
            })}
          </div>

          {node && (
            <p className="mt-2.5 text-[11px] leading-relaxed text-text-secondary">
              {node.detail}
            </p>
          )}
          {!node && !compact && (
            <p className="mt-2.5 text-[10px] leading-relaxed text-text-tertiary">
              To nie jest lista do odhaczenia. To kompas — wejdź z dowolnego
              elementu.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default FragmentCompass;
