import { useCallback, useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { useLang } from "@/lib/i18n";

interface Row {
  id: number;
  text: string;
  status: string;
  created_at: string;
  follow_up_at?: string | null;
  trigger_type?: string;
  needs_attention?: number;
}

export function CommitmentsTimeline({ projectId }: { projectId: number }) {
  const { t } = useLang();
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState<number | null>(null);
  const [note, setNote] = useState<Record<number, string>>({});
  const [link, setLink] = useState<Record<number, string>>({});

  const load = useCallback(() => {
    fetch(`${getApiBase()}/projects/${projectId}/commitments`, {
      headers: { ...getApiAuthHeaders() },
    })
      .then((r) => r.json())
      .then((d) => setRows(d.commitments ?? []))
      .catch(() => setRows([]));
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  async function check(id: number) {
    setBusy(id);
    try {
      const res = await fetch(`${getApiBase()}/commitment/${id}/complete`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          ...getApiAuthHeaders(),
        },
        body: JSON.stringify({
          evidence_note: note[id]?.trim() || undefined,
          evidence_url: link[id]?.trim() || undefined,
        }),
      });
      if (res.ok) load();
    } finally {
      setBusy(null);
    }
  }

  if (!rows.length) {
    return (
      <p className="text-[11px] text-white/25 px-1 py-2">{t("commitments.timeline.empty")}</p>
    );
  }

  return (
    <section className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3 mt-4">
      <h3 className="text-[11px] uppercase tracking-widest text-white/35 mb-3">
        {t("commitments.timeline.title")}
      </h3>
      <ol className="space-y-3 border-l border-white/10 ml-1.5 pl-4">
        {[...rows].reverse().map((r) => (
          <li key={r.id} className="relative">
            <span className="absolute -left-[21px] top-1.5 w-2 h-2 rounded-full bg-teal/50 border border-teal/80" />
            <div className="text-[10px] text-white/30 font-mono mb-0.5">
              #{r.id} · {r.created_at?.slice(0, 16) ?? ""}
              {r.follow_up_at && (
                <span className="text-amber-200/70"> · FU {r.follow_up_at.slice(0, 10)}</span>
              )}
            </div>
            <p className="text-[12px] text-white/75 leading-snug whitespace-pre-wrap">{r.text}</p>
            <div className="mt-1.5 flex flex-wrap gap-2 items-center">
              <span
                className={`text-[10px] px-1.5 py-0.5 rounded border ${
                  r.status === "open"
                    ? "border-teal/30 text-teal/90"
                    : "border-white/15 text-white/35"
                }`}
              >
                {r.status}
                {r.needs_attention ? " · !" : ""}
              </span>
              {r.status === "open" && (
                <>
                  <input
                    type="text"
                    placeholder={t("commitments.timeline.note_ph")}
                    value={note[r.id] ?? ""}
                    onChange={(e) => setNote((m) => ({ ...m, [r.id]: e.target.value }))}
                    className="flex-1 min-w-[120px] max-w-[200px] bg-black/30 border border-white/10 rounded px-2 py-1 text-[11px] text-white"
                  />
                  <input
                    type="url"
                    placeholder={t("commitments.timeline.url_ph")}
                    value={link[r.id] ?? ""}
                    onChange={(e) => setLink((m) => ({ ...m, [r.id]: e.target.value }))}
                    className="flex-1 min-w-[100px] max-w-[180px] bg-black/30 border border-white/10 rounded px-2 py-1 text-[11px] text-white"
                  />
                  <button
                    type="button"
                    disabled={busy === r.id}
                    onClick={() => void check(r.id)}
                    className="text-[11px] px-2 py-1 rounded border border-teal/40 text-teal hover:bg-teal/15 disabled:opacity-40"
                  >
                    {busy === r.id ? "…" : t("commitments.timeline.check")}
                  </button>
                </>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
