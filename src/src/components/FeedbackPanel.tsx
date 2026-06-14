/**
 * Feedback panel dla soft launchu (Tydzień 4 mapy luk).
 *
 * 3 pytania, niskotarczowy UX. Trigger: ręczny przycisk w UI ALBO po
 * domknięciu debaty (opóźniony w App.tsx — AX2 ma pierwszeństwo).
 * Payload: POST /feedback → DB z RLS per tenant (0003_feedback_table.sql).
 */

import { useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { useLang } from "@/lib/i18n";

type Props = {
  open: boolean;
  debateId?: number;
  onClose: (submitted: boolean) => void;
};

export function FeedbackPanel({ open, debateId, onClose }: Props) {
  const { t } = useLang();
  const [rating, setRating] = useState<number>(0);
  const [worked, setWorked] = useState("");
  const [broke, setBroke] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    const first = panelRef.current?.querySelector<HTMLElement>(
      "button, textarea, [href], input",
    );
    first?.focus();

    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCloseRef.current(false);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  const submit = async () => {
    if (rating < 1) {
      setErr(t("fb.err_rating"));
      return;
    }
    setSending(true);
    setErr(null);
    try {
      const r = await fetch(`${getApiBase()}/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getApiAuthHeaders(),
        },
        body: JSON.stringify({
          rating,
          what_worked: worked,
          what_broke: broke,
          debate_id: debateId ?? null,
        }),
      });
      if (!r.ok) {
        setErr(`Błąd: HTTP ${r.status}`);
        return;
      }
      onClose(true);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setSending(false);
    }
  };

  return (
    <div
      className="no-print fixed inset-0 z-[55] flex items-center justify-center bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="feedback-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose(false);
      }}
    >
      <div
        ref={panelRef}
        className="w-full max-w-lg mx-4 rounded-2xl border border-white/10 bg-navy/95 p-6 shadow-2xl"
      >
        <div className="flex items-center justify-between mb-3">
          <span className="text-[11px] uppercase tracking-widest text-white/40">
            Soft launch · feedback
          </span>
          <button
            type="button"
            onClick={() => onClose(false)}
            className="text-white/35 hover:text-white/80 text-sm"
          >
            {t("onb.later")}
          </button>
        </div>

        <h2 id="feedback-title" className="text-[17px] text-white mb-1">
          {t("fb.title")}
        </h2>
        <p className="text-[12px] text-white/50 mb-4">
          {t("fb.subtitle")}
        </p>

        <div className="mb-4">
          <label className="block text-[11px] uppercase tracking-wide text-white/50 mb-2">
            {t("fb.rating_label")}
          </label>
          <div className="flex items-center gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setRating(n)}
                aria-pressed={rating === n}
                className={
                  "w-9 h-9 rounded-full text-[14px] border transition " +
                  (rating >= n
                    ? "bg-teal/20 border-teal/50 text-teal"
                    : "bg-white/[0.02] border-white/10 text-white/40 hover:border-white/30")
                }
              >
                {n}
              </button>
            ))}
          </div>
        </div>

        <label className="block text-[11px] uppercase tracking-wide text-white/50 mb-1">
          {t("fb.worked_label")}
        </label>
        <textarea
          rows={2}
          value={worked}
          onChange={(e) => setWorked(e.target.value)}
          placeholder={t("fb.worked_ph")}
          className="w-full bg-white/[0.04] border border-white/10 rounded-lg p-3 text-[13px] focus:outline-none focus:border-teal/50 mb-3"
        />

        <label className="block text-[11px] uppercase tracking-wide text-white/50 mb-1">
          {t("fb.broke_label")}
        </label>
        <textarea
          rows={2}
          value={broke}
          onChange={(e) => setBroke(e.target.value)}
          placeholder={t("fb.broke_ph")}
          className="w-full bg-white/[0.04] border border-white/10 rounded-lg p-3 text-[13px] focus:outline-none focus:border-teal/50"
        />

        {err && (
          <p className="mt-3 text-[12px] text-amber-300" role="alert">
            {err}
          </p>
        )}

        <div className="flex justify-end mt-5">
          <button
            type="button"
            onClick={() => void submit()}
            disabled={sending}
            className="text-[12px] px-4 py-2 rounded-full bg-teal/20 border border-teal/50 text-teal hover:bg-teal/30 disabled:opacity-50"
          >
            {sending ? t("fb.sending") : t("fb.send")}
          </button>
        </div>
      </div>
    </div>
  );
}

export default FeedbackPanel;
