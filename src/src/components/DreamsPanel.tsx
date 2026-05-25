import { useEffect, useState } from "react";
import { isCouncilFa2 } from "@/config/product";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { useLang } from "@/lib/i18n";

interface FunctionalityItem {
  id: number;
  description: string;
  is_done: 0 | 1 | boolean;
}

interface DreamRow {
  id: string;
  core_dream: string;
  status: string;
  created_at: string;
}

interface ProjectRow {
  id: number;
  status: string;
  functionality: FunctionalityItem[];
}

interface DreamWithProject extends DreamRow {
  project?: ProjectRow | null;
  open_commitments_count?: number;
  next_follow_up_at?: string | null;
  days_since_progress?: number | null;
}

const MIN_REASON = 50;

function statusColor(status?: string): string {
  switch (status) {
    case "completed": return "text-green-400";
    case "archived_consciously": return "text-white/25 line-through";
    case "at_risk": return "text-amber-400";
    case "stuck": return "text-red-400";
    case "in_progress": return "text-teal";
    default: return "text-white/40";
  }
}

function statusLabel(status: string, lang: string): string {
  const map: Record<string, { pl: string; en: string }> = {
    dreaming: { pl: "marzy", en: "dreaming" },
    in_progress: { pl: "w toku", en: "in progress" },
    at_risk: { pl: "zagrożony", en: "at risk" },
    stuck: { pl: "utknął", en: "stuck" },
    completed: { pl: "ukończony", en: "completed" },
    archived_consciously: { pl: "zarchiwizowany", en: "archived" },
  };
  return map[status]?.[lang as "pl" | "en"] ?? status;
}

export function DreamsPanel({ disabled }: { disabled: boolean }) {
  const { lang, t } = useLang();
  const [open, setOpen] = useState(false);
  const [dreams, setDreams] = useState<DreamWithProject[]>([]);
  const [loading, setLoading] = useState(false);
  const [archiving, setArchiving] = useState<number | null>(null);
  const [archiveReason, setArchiveReason] = useState("");
  const [archiveErr, setArchiveErr] = useState<string | null>(null);

  const isPL = lang === "pl";

  function load() {
    setLoading(true);
    fetch(`${getApiBase()}/dreams?limit=30`, {
      headers: { ...getApiAuthHeaders() },
    })
      .then((r) => r.json())
      .then((data) => setDreams(data.dreams ?? []))
      .catch(() => setDreams([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (open) load();
  }, [open]);

  async function handleArchive(projectId: number) {
    if (archiveReason.trim().length < MIN_REASON) return;
    setArchiveErr(null);
    try {
      const res = await fetch(`${getApiBase()}/projects/${projectId}/archive`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getApiAuthHeaders(),
        },
        body: JSON.stringify({ reason: archiveReason.trim() }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setArchiveErr(String(err?.detail ?? res.status));
        return;
      }
      setArchiving(null);
      setArchiveReason("");
      load();
    } catch (e) {
      setArchiveErr(String(e));
    }
  }

  const label = isCouncilFa2()
    ? isPL
      ? "Projekty (FA2)"
      : "Projects (FA2)"
    : isPL
      ? "Moje marzenia"
      : "My dreams";

  return (
    <div className="mt-4">
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-[11px] uppercase tracking-widest text-white/30 hover:text-teal/70 transition-colors disabled:opacity-40"
      >
        <span>{label}</span>
        <span>{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="mt-2 space-y-2">
          {loading && (
            <p className="text-[11px] text-white/30 px-1">{isPL ? "Ładuję..." : "Loading..."}</p>
          )}
          {!loading && dreams.length === 0 && (
            <p className="text-[11px] text-white/25 px-1">
              {isPL ? "Brak marzeń — zacznij debatę." : "No dreams yet — start a debate."}
            </p>
          )}

          {dreams.map((d) => {
            const proj = d.project;
            const isArchived = proj?.status === "archived_consciously";
            const items = proj?.functionality ?? [];
            const done = items.filter((f) => f.is_done).length;
            const pct = items.length ? Math.round((done / items.length) * 100) : 0;
            const isArchivingThis = archiving === proj?.id;
            const canArchive = proj && !isArchived && proj.status !== "completed";

            const openCm = d.open_commitments_count ?? 0;
            const nextFu = d.next_follow_up_at;
            const fuSoon =
              nextFu &&
              (() => {
                try {
                  const dt = new Date(nextFu).getTime();
                  const h72 = 72 * 3600 * 1000;
                  return dt - Date.now() < h72;
                } catch {
                  return false;
                }
              })();

            return (
              <div
                key={d.id}
                className={`rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5 ${isArchived ? "opacity-40" : ""}`}
              >
                {proj?.status === "stuck" && (
                  <div className="mb-2 rounded border border-red-500/35 bg-red-950/25 px-2 py-1.5 text-[10px] text-red-200/95 leading-snug">
                    {t("dreams.stuck.banner")}
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="min-w-0">
                    <div className="text-[9px] uppercase tracking-widest text-white/30 mb-1">
                      {t("dreams.col.dream")}
                    </div>
                    <p className="text-[12px] text-white/78 leading-snug line-clamp-4">
                      {d.core_dream}
                    </p>
                  </div>

                  <div className="min-w-0 flex flex-col gap-2">
                    <div className="text-[9px] uppercase tracking-widest text-white/30">
                      {t("dreams.col.progress")}
                    </div>
                    {proj ? (
                      <>
                        <div className="flex items-center gap-2">
                          <div className="relative w-11 h-11 shrink-0 rounded-full border border-white/15 flex items-center justify-center text-[11px] font-medium text-teal">
                            {pct}%
                          </div>
                          <div>
                            <div className={`text-[12px] font-medium ${statusColor(proj.status)}`}>
                              {statusLabel(proj.status, lang)}
                            </div>
                            <div className="text-[10px] text-white/35">
                              {done}/{items.length}
                            </div>
                          </div>
                        </div>
                        <div className="text-[10px] text-white/40">
                          {openCm}{" "}
                          <span className="text-white/55">{t("dreams.open_commitments")}</span>
                        </div>
                      </>
                    ) : (
                      <p className="text-[10px] text-white/25">—</p>
                    )}
                  </div>

                  <div className="min-w-0">
                    <div className="text-[9px] uppercase tracking-widest text-white/30 mb-1">
                      {t("dreams.col.next")}
                    </div>
                    {nextFu ? (
                      <div
                        className={`inline-flex flex-col gap-0.5 rounded border px-2 py-1 text-[10px] ${
                          fuSoon
                            ? "border-amber-500/50 bg-amber-500/10 text-amber-100/95"
                            : "border-white/10 bg-white/[0.03] text-white/55"
                        }`}
                        title={nextFu}
                      >
                        <span>{t("dreams.next_followup")}</span>
                        <span className="font-mono text-[9px] opacity-80">
                          {nextFu.slice(0, 16)}…
                        </span>
                      </div>
                    ) : (
                      <p className="text-[10px] text-white/25">—</p>
                    )}
                    {typeof d.days_since_progress === "number" && (
                      <div
                        className={`mt-1.5 inline-flex text-[9px] px-1.5 py-0.5 rounded border font-mono ${
                          d.days_since_progress >= 30
                            ? "border-red-500/40 text-red-300/90 bg-red-950/20"
                            : d.days_since_progress >= 14
                              ? "border-amber-500/35 text-amber-200/90 bg-amber-950/15"
                              : "border-white/12 text-white/45"
                        }`}
                        title={isPL ? `Ostatni ruch: ${d.days_since_progress} dni temu` : `Last move: ${d.days_since_progress}d ago`}
                      >
                        Δ{d.days_since_progress}d
                      </div>
                    )}
                  </div>
                </div>

                {proj && (
                  <>
                    <div className="flex items-center gap-2 mt-2 mb-0.5">
                      <div className="flex-1 h-1 bg-white/10 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-teal rounded-full transition-all"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>

                    {canArchive && !isArchivingThis && (
                      <button
                        type="button"
                        onClick={() => { setArchiving(proj.id); setArchiveReason(""); setArchiveErr(null); }}
                        className="text-[10px] text-white/25 hover:text-amber-400/70 transition-colors"
                      >
                        {isPL ? "archiwizuj świadomie" : "archive consciously"}
                      </button>
                    )}
                  </>
                )}

                {isArchivingThis && (
                  <div className="mt-2 space-y-1.5">
                    <textarea
                      value={archiveReason}
                      onChange={(e) => setArchiveReason(e.target.value)}
                      placeholder={isPL
                        ? "Dlaczego odpuszczasz? (min. 50 znaków)"
                        : "Why are you letting go? (min. 50 chars)"}
                      rows={2}
                      className="w-full bg-white/5 border border-white/10 rounded px-2 py-1.5 text-[11px] text-white placeholder:text-white/20 resize-none focus:outline-none focus:border-amber-500/40"
                    />
                    <div className="flex items-center gap-2">
                      <span className={`text-[10px] font-mono ${archiveReason.trim().length >= MIN_REASON ? "text-teal" : "text-white/25"}`}>
                        {archiveReason.trim().length}/{MIN_REASON}
                      </span>
                      <button
                        type="button"
                        disabled={archiveReason.trim().length < MIN_REASON}
                        onClick={() => handleArchive(proj!.id)}
                        className="text-[10px] px-2 py-0.5 rounded border border-amber-500/30 text-amber-400/80 hover:bg-amber-500/10 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                      >
                        {isPL ? "potwierdź" : "confirm"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setArchiving(null)}
                        className="text-[10px] text-white/25 hover:text-white/50 transition-colors"
                      >
                        {isPL ? "anuluj" : "cancel"}
                      </button>
                    </div>
                    {archiveErr && (
                      <p className="text-[10px] text-red-400">{archiveErr}</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
