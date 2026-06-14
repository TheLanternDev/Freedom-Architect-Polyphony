import { useEffect, useMemo, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { SidebarSection } from "@/components/ui/SidebarSection";
import { LS_ONBOARDING_DONE } from "@/components/PersonalRitualPanels";
import { useLang } from "@/lib/i18n";

/**
 * MojObrazPanel — żywy obraz użytkownika (Zadanie B).
 *
 * Synteza onboardingu: odpowiedzi zgrupowane w sekcje (Tożsamość, Cień, …),
 * z możliwością edycji i ponownego zapisu. To trwały model, do którego user
 * może wracać. Źródło: GET /personal/onboarding/answers; zapis: /save (upsert).
 */

interface AnswerRow {
  question_idx: number;
  answer: string;
  updated_at?: string | null;
}
interface Payload {
  items: string[];
  sekcje: string[];
  answers: AnswerRow[];
}

interface ObrazModel {
  wartosci: string[];
  napiecia: string[];
  relacje: string[];
  wzorce: string[];
  cialo: string;
  kreatywnosc: string;
  duchowosc: string;
  potrzeba_teraz: string;
  zdanie_dla_siebie: string;
  wersja: number;
  zrodlo: string;
}
interface ObrazResp {
  obraz: ObrazModel | null;
  wersja: number | null;
  updated_at: string | null;
}

export function MojObrazPanel() {
  const { t } = useLang();
  const [data, setData] = useState<Payload | null>(null);
  const [edited, setEdited] = useState<Record<number, string>>({});
  const [busy, setBusy] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [obraz, setObraz] = useState<ObrazResp | null>(null);
  const [obrazBusy, setObrazBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${getApiBase()}/personal/onboarding/answers`, {
          headers: getApiAuthHeaders(),
        });
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const j = (await r.json()) as Payload;
        if (cancelled) return;
        setData(j);
        const init: Record<number, string> = {};
        for (const a of j.answers ?? []) init[a.question_idx] = a.answer ?? "";
        setEdited(init);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : t("obraz.err.load"));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Grupowanie indeksów wg sekcji, z zachowaniem kolejności.
  const groups = useMemo(() => {
    if (!data) return [] as Array<{ name: string; idxs: number[] }>;
    const out: Array<{ name: string; idxs: number[] }> = [];
    data.sekcje.forEach((name, i) => {
      const last = out[out.length - 1];
      if (last && last.name === name) last.idxs.push(i);
      else out.push({ name, idxs: [i] });
    });
    return out;
  }, [data]);

  const answeredCount = useMemo(
    () => Object.values(edited).filter((v) => v && v.trim()).length,
    [edited],
  );

  const save = async () => {
    if (!data) return;
    setBusy(true);
    setErr(null);
    try {
      const answers = Object.entries(edited)
        .filter(([, v]) => v && v.trim())
        .map(([k, v]) => ({ question_idx: Number(k), answer: v.trim() }));
      const r = await fetch(`${getApiBase()}/personal/onboarding/save`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getApiAuthHeaders() },
        body: JSON.stringify({ answers }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSavedAt(new Date().toLocaleTimeString().slice(0, 5));
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("obraz.err.save"));
    } finally {
      setBusy(false);
    }
  };

  // Zdestylowany Obraz („Obraz, który Rada widzi") — GET na starcie.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${getApiBase()}/personal/onboarding/obraz`, {
          headers: getApiAuthHeaders(),
        });
        if (!r.ok) return;
        const j = (await r.json()) as ObrazResp;
        if (!cancelled) setObraz(j);
      } catch {
        /* miękko — sekcja Obrazu jest opcjonalna */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const synthesize = async () => {
    setObrazBusy(true);
    setErr(null);
    try {
      const r = await fetch(`${getApiBase()}/personal/onboarding/synthesize`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getApiAuthHeaders() },
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as { obraz: ObrazModel; wersja: number };
      setObraz({ obraz: j.obraz, wersja: j.wersja, updated_at: new Date().toISOString() });
    } catch (e) {
      setErr(e instanceof Error ? e.message : t("obraz.err.synth"));
    } finally {
      setObrazBusy(false);
    }
  };

  const redoOnboarding = () => {
    try {
      localStorage.removeItem(LS_ONBOARDING_DONE);
    } catch {
      /* ignore */
    }
    window.location.reload();
  };

  return (
    <SidebarSection label={t("obraz.section")} className="flex flex-col min-h-0 h-full">
      <div className="flex flex-col min-h-0 flex-1">
        <p className="shrink-0 text-[10px] text-text-tertiary leading-snug mb-2">
          {t("obraz.lead")}{" "}
          {data && <span className="text-gold/60">{answeredCount}/{data.items.length}</span>}
        </p>
        {err && <p className="shrink-0 text-[11px] text-amber-400/80 mb-2">{err}</p>}

        <div className="min-h-0 flex-1 overflow-y-auto aw-scroll -mx-0.5 px-0.5 space-y-4">
          {(() => {
            const o = obraz?.obraz ?? null;
            const list = (xs: string[]) => (xs ?? []).filter((x) => x && x.trim()).join("; ");
            const rows: Array<[string, string]> = o
              ? ([
                  [t("obraz.row.values"), list(o.wartosci)],
                  [t("obraz.row.tensions"), list(o.napiecia)],
                  [t("obraz.row.relations"), list(o.relacje)],
                  [t("obraz.row.patterns"), list(o.wzorce)],
                  [t("obraz.row.body"), o.cialo],
                  [t("obraz.row.creativity"), o.kreatywnosc],
                  [t("obraz.row.spirituality"), o.duchowosc],
                  [t("obraz.row.need_now"), o.potrzeba_teraz],
                ].filter(([, v]) => v && v.trim()) as Array<[string, string]>)
              : [];
            const empty = !o || (rows.length === 0 && !o.zdanie_dla_siebie?.trim());
            return (
              <div className="rounded-control border border-gold/25 bg-gold/[0.05] px-3 py-2.5">
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[10px] uppercase tracking-[0.2em] text-gold/70">
                    {t("obraz.council_sees")}
                  </span>
                  <button
                    type="button"
                    onClick={() => void synthesize()}
                    disabled={obrazBusy}
                    className="text-[10px] px-2 py-0.5 rounded-control border border-gold/40 text-gold/90 hover:bg-gold/15 disabled:opacity-40 transition-colors"
                  >
                    {obrazBusy ? t("obraz.btn.distilling") : o ? t("obraz.btn.refresh") : t("obraz.btn.synthesize")}
                  </button>
                </div>
                {empty ? (
                  <p className="text-[11px] text-text-tertiary leading-snug">
                    {t("obraz.empty")}
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {o?.zdanie_dla_siebie?.trim() && (
                      <p className="font-serif italic text-[13px] leading-snug text-[#E8D5A3]">
                        „{o.zdanie_dla_siebie}”
                      </p>
                    )}
                    {rows.map(([label, value]) => (
                      <div key={label} className="leading-snug">
                        <span className="text-[9px] uppercase tracking-wider text-teal/70">
                          {label}:{" "}
                        </span>
                        <span className="text-[11px] text-text-secondary">{value}</span>
                      </div>
                    ))}
                    {obraz?.wersja != null && (
                      <p className="text-[9px] text-text-tertiary pt-0.5">
                        {t("obraz.version")} {obraz.wersja}
                      </p>
                    )}
                  </div>
                )}
              </div>
            );
          })()}

          {groups.map((g) => (
            <div key={g.name}>
              <div className="text-[10px] uppercase tracking-[0.2em] text-teal/70 mb-1.5">
                {g.name}
              </div>
              <div className="space-y-2.5">
                {g.idxs.map((i) => (
                  <div key={i}>
                    <p className="text-[11px] text-text-secondary leading-snug mb-1">
                      {data?.items[i]}
                    </p>
                    <textarea
                      rows={2}
                      value={edited[i] ?? ""}
                      onChange={(e) =>
                        setEdited((m) => ({ ...m, [i]: e.target.value }))
                      }
                      placeholder="—"
                      className="w-full rounded-control bg-surface-raised/60 border border-border px-2.5 py-1.5 text-[12px] text-text-secondary placeholder:text-text-tertiary focus:outline-none focus:border-gold/40 resize-y"
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
          {!data && !err && (
            <p className="aw-caption">{t("obraz.loading")}</p>
          )}
        </div>

        <div className="shrink-0 pt-3 mt-2 border-t border-border flex items-center gap-2">
          <button
            type="button"
            onClick={() => void save()}
            disabled={busy || !data}
            className="text-[12px] px-4 py-2 rounded-control bg-gold/20 border border-gold/50 text-gold font-medium hover:bg-gold/30 disabled:opacity-35 transition-colors"
          >
            {busy ? t("obraz.btn.saving") : t("obraz.btn.save")}
          </button>
          {savedAt && <span className="text-[10px] text-teal/70">{t("obraz.saved")} {savedAt}</span>}
          <button
            type="button"
            onClick={redoOnboarding}
            className="ml-auto text-[10px] text-text-tertiary hover:text-text-secondary underline-offset-2 hover:underline"
          >
            {t("obraz.redo")}
          </button>
        </div>
      </div>
    </SidebarSection>
  );
}
