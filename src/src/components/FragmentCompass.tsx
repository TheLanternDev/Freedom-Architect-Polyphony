/**
 * AKSJOMAT 0 w UI — kompas Filozofii Fragmentu.
 *
 * To NIE jest todo. To kompas — stale widoczna mała ramka, która pokazuje
 * trzy elementy systemu (Uśmiech ↔ Perspektywa ↔ Droga) jako żywy, samopod-
 * trzymujący się układ. Klik w element rozwija krótki opis. Brak progresu,
 * brak procentów, brak "zaznacz jako zrobione" — bo to jest postawa, nie cel.
 *
 * Plik czytany razem z `core/dream_architect.py:Fragment` i `CLAUDE.md` (sekcja
 * AKSJOMAT 0). Każda zmiana wizualnego centrum systemu MUSI zachowywać
 * symetrię trzech elementów (żaden nie jest "pierwszy").
 */

import { useState } from "react";

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
  const node = active ? NODES.find((n) => n.key === active) ?? null : null;

  return (
    <div
      className={
        "rounded-2xl border border-white/10 bg-white/[0.03] " +
        (compact ? "p-3" : "p-4")
      }
      aria-label="Fragment — kompas (Uśmiech, Perspektywa, Droga)"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] uppercase tracking-widest text-white/40">
          Fragment · kompas
        </span>
        <span className="text-[10px] text-white/30" title="AKSJOMAT 0">
          AKSJOMAT 0
        </span>
      </div>

      <div className="flex items-stretch gap-2">
        {NODES.map((n) => {
          const isActive = active === n.key;
          return (
            <button
              key={n.key}
              onClick={() => setActive(isActive ? null : n.key)}
              className={
                "flex-1 rounded-xl border px-3 py-2 text-left transition " +
                (isActive
                  ? "border-teal/50 bg-teal/10"
                  : "border-white/10 bg-white/[0.02] hover:border-white/25")
              }
              aria-pressed={isActive}
            >
              <div className="text-xl leading-none mb-1" aria-hidden>
                {n.icon}
              </div>
              <div className="text-[13px] font-medium text-white/90">
                {n.pl}
              </div>
              {!compact && (
                <div className="text-[11px] text-white/45 mt-0.5">
                  {n.short}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {node && (
        <p className="mt-3 text-[12px] leading-relaxed text-white/70">
          {node.detail}
        </p>
      )}
      {!node && !compact && (
        <p className="mt-3 text-[11px] leading-relaxed text-white/35">
          To nie jest lista do odhaczenia. To kompas. Każdy element zasila
          dwa pozostałe — wejdź z dowolnego.
        </p>
      )}
    </div>
  );
}

export default FragmentCompass;
