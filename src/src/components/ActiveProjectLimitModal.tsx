/**
 * Konfrontacja AKSJOMATU 2 w UI — pełnoekranowy modal gdy backend zwraca
 * `CompletionViolation(kind="active_project_limit")` (HTTP 409).
 *
 * Cel: NIE pokazywać tego jako zwykłego błędu („Active project limit reached").
 * System świadomie staje przed Patrykiem i prosi o decyzję: kończysz X /
 * archiwizujesz świadomie X / rezygnujesz z nowego projektu. „Brak ruchu"
 * NIE jest opcją — to dokładnie ten wzorzec, który system ma blokować.
 *
 * Sygnatura `details` zgodna z `core.completion_enforcer.CompletionViolation`:
 *   {
 *     limit: number,
 *     active_projects: Array<{
 *       id: number, dream_id: string, status: string,
 *       completion_ratio: number, days_since_progress: number | null
 *     }>
 *   }
 */

import { useState } from "react";

export type ActiveProjectInfo = {
  id: number;
  dream_id: string;
  status: string;
  completion_ratio: number;
  days_since_progress: number | null;
};

type Props = {
  open: boolean;
  limit: number;
  activeProjects: ActiveProjectInfo[];
  onFinish: (projectId: number) => void;
  onArchive: (projectId: number) => void;
  onCancel: () => void;
};

export function ActiveProjectLimitModal(props: Props) {
  const { open, limit, activeProjects, onFinish, onArchive, onCancel } = props;
  const [selectedId, setSelectedId] = useState<number | null>(
    activeProjects[0]?.id ?? null
  );

  if (!open) return null;

  const selected = activeProjects.find((p) => p.id === selectedId) ?? null;

  return (
    <div
      className="no-print fixed inset-0 z-[60] flex items-center justify-center bg-black/80 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="apl-title"
    >
      <div className="w-full max-w-2xl mx-4 rounded-2xl border border-amber-500/30 bg-navy/95 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-widest text-amber-400/80">
            AKSJOMAT 2 · konfrontacja
          </span>
          <span className="text-[11px] text-white/30">limit: {limit}</span>
        </div>

        <h2 id="apl-title" className="text-[19px] leading-snug text-white mb-2">
          Masz {activeProjects.length}{" "}
          {activeProjects.length === 1 ? "aktywny projekt" : "aktywne projekty"}.
          Najpierw skończ lub świadomie zarchiwizuj.
        </h2>
        <p className="text-[13px] text-white/55 mb-4">
          To nie jest błąd. System świadomie się zatrzymuje, żeby nie powtórzył
          wzorca „zacznij i porzuć". Wybierz jeden ruch poniżej —{" "}
          <em>brak ruchu</em> to dokładnie ten wzorzec.
        </p>

        <div className="space-y-2 mb-5 max-h-64 overflow-auto pr-1">
          {activeProjects.map((p) => {
            const isSel = p.id === selectedId;
            const pct = Math.round((p.completion_ratio || 0) * 100);
            return (
              <button
                key={p.id}
                onClick={() => setSelectedId(p.id)}
                className={
                  "w-full text-left rounded-xl border px-3 py-2 transition " +
                  (isSel
                    ? "border-teal/50 bg-teal/10"
                    : "border-white/10 bg-white/[0.02] hover:border-white/25")
                }
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[13px] text-white/90 font-medium truncate">
                      #{p.id} · {p.dream_id}
                    </div>
                    <div className="text-[11px] text-white/40">
                      status: {p.status} · {pct}% checklist
                      {p.days_since_progress != null && (
                        <> · {p.days_since_progress} dni bez ruchu</>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            onClick={() => selected && onFinish(selected.id)}
            disabled={!selected}
            className="text-[12px] px-3 py-2 rounded-full bg-teal/20 border border-teal/50 text-teal hover:bg-teal/30 disabled:opacity-30"
          >
            Kończę #{selected?.id ?? "—"} (otwórz checklistę)
          </button>
          <button
            onClick={() => selected && onArchive(selected.id)}
            disabled={!selected}
            className="text-[12px] px-3 py-2 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 disabled:opacity-30"
            title="Wymaga uzasadnienia min. 50 znaków (świadoma archiwizacja)."
          >
            Archiwizuję świadomie #{selected?.id ?? "—"}
          </button>
          <div className="grow" />
          <button
            onClick={onCancel}
            className="text-[12px] text-white/40 hover:text-white/80"
          >
            Rezygnuję z nowego
          </button>
        </div>

        <p className="mt-4 text-[10px] text-white/30 leading-relaxed">
          „Wrócimy do tego" bez warunku powrotu = porzucenie. Świadoma
          archiwizacja wymaga konkretu (data + powód) — to nie jest tylna furtka.
        </p>
      </div>
    </div>
  );
}

export default ActiveProjectLimitModal;
