import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { useLang } from "@/lib/i18n";
import { CommitmentExportButtons } from "@/components/CommitmentExportButtons";

/**
 * DebateCommitments — read-only przegląd zobowiązań danej debaty (Zadanie C).
 *
 * W przeciwieństwie do CommitmentsTimeline (interaktywna, per-projekt) ten
 * widok działa dla KAŻDEJ debaty — także decyzji bez marzenia/projektu oraz
 * dla wcześniejszych tur wątku w historii. Źródło: GET /debate/{id} →
 * `commitments` (utrwalone). Nie modyfikuje stanu — czysty przegląd.
 */

interface Row {
  id: number;
  text: string;
  status: string;
  created_at?: string;
  follow_up_at?: string | null;
}

export function DebateCommitments({ debateId }: { debateId: number }) {
  const { t } = useLang();
  const [rows, setRows] = useState<Row[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetch(`${getApiBase()}/debate/${debateId}`, {
      headers: { ...getApiAuthHeaders() },
    })
      .then((r) => (r.ok ? r.json() : { commitments: [] }))
      .then((d) => {
        if (!cancelled) setRows(Array.isArray(d?.commitments) ? d.commitments : []);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      });
    return () => {
      cancelled = true;
    };
  }, [debateId]);

  if (!rows.length) return null;

  return (
    <section className="rounded-xl border border-gold/15 bg-white/[0.02] px-4 py-3 mt-4">
      <h3 className="text-[11px] uppercase tracking-widest text-gold/45 mb-3">
        {t("commitments.timeline.title")}
      </h3>
      <ol className="space-y-3 border-l border-gold/15 ml-1.5 pl-4">
        {[...rows].reverse().map((r) => (
          <li key={r.id} className="relative">
            <span className="absolute -left-[21px] top-1.5 w-2 h-2 rounded-full bg-gold/50 border border-gold/80" />
            <div className="text-[10px] text-white/30 font-mono mb-0.5">
              #{r.id}
              {r.created_at ? ` · ${r.created_at.slice(0, 16)}` : ""}
              {r.follow_up_at && (
                <span className="text-amber-200/70"> · FU {r.follow_up_at.slice(0, 10)}</span>
              )}
            </div>
            <p className="text-[12px] text-white/80 leading-snug whitespace-pre-wrap">
              {r.text}
            </p>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <span
                className={`inline-block text-[10px] px-1.5 py-0.5 rounded border ${
                  r.status === "open"
                    ? "border-teal/30 text-teal/90"
                    : "border-white/15 text-white/35"
                }`}
              >
                {r.status}
              </span>
              {r.status === "open" && <CommitmentExportButtons commitmentId={r.id} />}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
