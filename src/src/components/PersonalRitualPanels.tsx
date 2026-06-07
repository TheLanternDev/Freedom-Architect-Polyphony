import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { SidebarSection } from "@/components/ui/SidebarSection";

export const LS_ONBOARDING_DONE = "aw_onboarding_v1_done";

type Answers = Record<number, string>;

export function OnboardingPanel() {
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined") return false;
    try { return localStorage.getItem(LS_ONBOARDING_DONE) !== "1"; }
    catch { return false; }
  });
  const [items, setItems] = useState<string[]>([]);
  const [sekcje, setSekcje] = useState<string[]>([]);
  const [idx, setIdx] = useState(0);
  const [ans, setAns] = useState<Answers>({});

  useEffect(() => {
    if (!open || items.length) return;
    (async () => {
      try {
        const r = await fetch(`${getApiBase()}/personal/onboarding/questions`, {
          headers: getApiAuthHeaders(),
        });
        if (!r.ok) return;
        const j = await r.json();
        if (Array.isArray(j.items)) setItems(j.items);
        if (Array.isArray(j.sekcje)) setSekcje(j.sekcje);
      } catch { /* ignore */ }
    })();
  }, [open, items.length]);

  if (!open || !items.length) return null;
  const total = items.length;
  const q = items[idx];
  const sekcja = sekcje[idx];
  // Pozycja pytania w obrębie sekcji (batch) — „inteligentne sekwencjonowanie".
  const sectionStart = sekcje.findIndex((s) => s === sekcja);
  const sectionLen = sekcje.filter((s) => s === sekcja).length;
  const inSection = sectionStart >= 0 ? idx - sectionStart + 1 : 0;
  const close = (done: boolean) => {
    if (done) {
      // Tydzień 4 / #14 tech-debt: na koniec onboardingu wysyłamy odpowiedzi
      // do backendu, żeby zasiliły AKSJOMAT 1 (Architektura Marzenia).
      // Best-effort — nie blokujemy zamknięcia modalu, gdy network padnie.
      const answers = Object.entries(ans)
        .filter(([, v]) => v && v.trim())
        .map(([k, v]) => ({ question_idx: Number(k), answer: v.trim() }));
      if (answers.length > 0) {
        fetch(`${getApiBase()}/personal/onboarding/save`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...getApiAuthHeaders() },
          body: JSON.stringify({ answers }),
        }).catch(() => { /* ignore — flaga localStorage chroni przed re-pytaniem */ });
      }
      try { localStorage.setItem(LS_ONBOARDING_DONE, "1"); } catch { /* ignore */ }
    }
    setOpen(false);
  };

  return (
    <div className="no-print fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-xl mx-4 rounded-2xl border border-gold/20 bg-surface/97 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-widest text-gold/55">
            Pierwsze uruchomienie · {idx + 1}/{total}
          </span>
          <button onClick={() => close(false)} className="text-white/35 hover:text-white/80 text-sm">
            Później
          </button>
        </div>
        {sekcja && (
          <div className="mb-2 text-[10px] uppercase tracking-[0.2em] text-teal/70">
            {sekcja}{sectionLen > 0 && <span className="text-white/30"> · {inSection}/{sectionLen}</span>}
          </div>
        )}
        <p className="text-[18px] leading-relaxed text-white mb-4">{q}</p>
        <textarea
          rows={3}
          value={ans[idx] ?? ""}
          onChange={(e) => setAns({ ...ans, [idx]: e.target.value })}
          placeholder="Odpowiedz w swoim tempie. Możesz pominąć."
          className="w-full bg-white/[0.04] border border-white/10 rounded-lg p-3 text-[14px] focus:outline-none focus:border-teal/50"
        />
        <div className="flex justify-between mt-4">
          <button
            disabled={idx === 0}
            onClick={() => setIdx(idx - 1)}
            className="text-[12px] text-white/40 disabled:opacity-30 hover:text-white/80"
          >
            ← Wstecz
          </button>
          {idx < total - 1 ? (
            <button
              onClick={() => setIdx(idx + 1)}
              className="text-[12px] px-4 py-1.5 rounded-full bg-teal/15 border border-teal/40 text-teal hover:bg-teal/25"
            >
              Dalej →
            </button>
          ) : (
            <button
              onClick={() => close(true)}
              className="text-[12px] px-4 py-1.5 rounded-full bg-teal/15 border border-teal/40 text-teal hover:bg-teal/25"
            >
              Zakończ
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function DailyRitualPanel() {
  const [data, setData] = useState<{ poranek: string[]; wieczor: string[] } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${getApiBase()}/personal/ritual/daily`, {
          headers: getApiAuthHeaders(),
        });
        if (!r.ok) return;
        setData(await r.json());
      } catch { /* ignore */ }
    })();
  }, []);

  if (!data) return null;
  const hour = new Date().getHours();
  const block = hour < 14 ? "poranek" : "wieczor";
  const list = block === "poranek" ? data.poranek : data.wieczor;
  const label = block === "poranek" ? "Rytuał poranny" : "Rytuał wieczorny";

  return (
    <SidebarSection label={label} collapsible className="no-print">
      <ul className="pt-1 space-y-2 text-[13px] text-text-secondary">
        {list.map((q, i) => (
          <li key={i} className="leading-relaxed pl-0.5">· {q}</li>
        ))}
      </ul>
    </SidebarSection>
  );
}
