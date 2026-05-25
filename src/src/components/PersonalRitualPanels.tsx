import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";

const LS_ONBOARDING_DONE = "aw_onboarding_v1_done";

type Answers = Record<number, string>;

export function OnboardingPanel() {
  const [open, setOpen] = useState(() => {
    if (typeof window === "undefined") return false;
    try { return localStorage.getItem(LS_ONBOARDING_DONE) !== "1"; }
    catch { return false; }
  });
  const [items, setItems] = useState<string[]>([]);
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
      } catch { /* ignore */ }
    })();
  }, [open, items.length]);

  if (!open || !items.length) return null;
  const total = items.length;
  const q = items[idx];
  const close = (done: boolean) => {
    if (done) {
      try { localStorage.setItem(LS_ONBOARDING_DONE, "1"); } catch { /* ignore */ }
    }
    setOpen(false);
  };

  return (
    <div className="no-print fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-xl mx-4 rounded-2xl border border-white/10 bg-navy/95 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-widest text-white/40">
            Pierwsze uruchomienie · {idx + 1}/{total}
          </span>
          <button onClick={() => close(false)} className="text-white/35 hover:text-white/80 text-sm">
            Później
          </button>
        </div>
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
  const [open, setOpen] = useState(false);

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
    <div className="no-print rounded-lg border border-white/10 bg-white/[0.02] p-3">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between text-[11px] uppercase tracking-widest text-white/40 hover:text-white/70"
      >
        <span>🌱 {label}</span>
        <span>{open ? "−" : "+"}</span>
      </button>
      {open && (
        <ul className="mt-3 space-y-2 text-[13px] text-white/75">
          {list.map((q, i) => (
            <li key={i} className="leading-relaxed">• {q}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
