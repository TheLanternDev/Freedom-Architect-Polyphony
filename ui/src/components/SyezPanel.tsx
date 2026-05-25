import { useCallback, useState, type FormEvent } from "react";
import type {
  DebateStatus,
  SynthesisStructuredPayload,
} from "@/types/debate";
import { MermaidBlock } from "@/components/MermaidBlock";
import { extractLikelyOpenQuestions } from "@/lib/openQuestions";
import { splitSynthesisSegments } from "@/lib/synthesisSegments";
import { useLang } from "@/lib/i18n";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";

interface Props {
  synthesis: string;
  synthesisStructured?: SynthesisStructuredPayload;
  status: DebateStatus;
  debateId?: number;
  debateCost?: number;
  /** Z `debate_start` — steruje domyślnym follow-up przy zapisie zobowiązania. */
  debateMode?: string;
  /** SSE `commitment_created` — auto zobowiązanie w trybie schematy. */
  lastCommitmentEcho?: Record<string, unknown> | null;
  onContinueThread?: (followUp: string) => void | Promise<void>;
  onCommitStep?: (
    text: string,
    due?: string,
    followUp?: string,
  ) => Promise<void>;
}

function synthesisToMarkdown(
  structured: SynthesisStructuredPayload | undefined,
  raw: string,
): string {
  let md = "# Syez Synthesis — Supervisory Council \"My World\"\n\n";
  if (!structured) {
    return md + raw.trim() + "\n";
  }
  if (structured.insights_per_agent?.length) {
    md += "## Perspectives overview\n\n";
    for (const row of structured.insights_per_agent) {
      md += `- **${row.agent}**: ${row.insight}\n`;
    }
    md += "\n";
  }
  if (structured.tensions?.length) {
    md += "## Tensions\n\n";
    for (const t of structured.tensions) {
      md += `- **${t.between?.join(" ↔ ") ?? "?"}**: ${t.why}\n`;
    }
    md += "\n";
  }
  if (structured.recommendations?.length) {
    md += "## Recommendations\n\n";
    for (const r of structured.recommendations) {
      md += `1. ${r}\n`;
    }
    md += "\n";
  }
  if (structured.open_questions?.length) {
    md += "## Open questions\n\n";
    for (const q of structured.open_questions) {
      md += `- ${q}\n`;
    }
    md += "\n";
  }
  if (structured.action_steps?.length) {
    md += "## Action steps\n\n";
    for (const a of structured.action_steps) {
      const due = a.due ? ` _(due: ${a.due})_` : "";
      md += `- [ ] ${a.step}${due}\n`;
    }
    md += "\n";
  }
  if (structured.commitments?.length) {
    md += "## Commitments (from the synthesis)\n\n";
    for (const c of structured.commitments) {
      md += `- ${c.text}${c.follow_up_at ? ` → follow-up: ${c.follow_up_at}` : ""}\n`;
    }
    md += "\n";
  }
  if (structured.completion_audit) {
    const ca = structured.completion_audit;
    md += "## Functionality audit\n\n";
    md +=
      "- Remaining checklist items: " +
      (ca.functionality_checklist_remaining?.join("; ") || "—") +
      "\n";
    md += "- Blockers: " + (ca.blocked_by?.join("; ") || "—") + "\n";
    md +=
      "- Smallest increment: " +
      (ca.smallest_next_functional_increment ?? "—") +
      "\n\n";
  }
  md += "---\n\n## Full text (mirror)\n\n```json\n";
  md += JSON.stringify(structured, null, 2);
  md += "\n```\n";
  return md;
}

function TensionBars({
  tensions,
}: {
  tensions: NonNullable<SynthesisStructuredPayload["tensions"]>;
}) {
  return (
    <div className="space-y-2">
      {tensions.map((t, i) => (
        <div key={i} className="border border-white/[0.07] rounded-lg px-3 py-2">
          <div className="text-[11px] text-teal/70 font-medium mb-1">
            {t.between?.join(" ↔ ") ?? "Tension"}
          </div>
          <p className="text-[12px] text-white/65 leading-snug">{t.why}</p>
        </div>
      ))}
    </div>
  );
}

export function SyezPanel({
  synthesis,
  synthesisStructured,
  status,
  debateId,
  debateCost,
  debateMode,
  lastCommitmentEcho,
  onContinueThread,
  onCommitStep,
}: Props) {
  const { t } = useLang();
  const isSynthesizing = status === "synthesizing";
  const isDone = status === "done";
  const isAgents = status === "agents_speaking";
  const isActive = isSynthesizing || isDone;

  const [committing, setCommitting] = useState<number | null>(null);
  const [commitErr, setCommitErr] = useState<string | null>(null);
  const [followUp, setFollowUp] = useState("");
  const [continuing, setContinuing] = useState(false);
  const [ownCommit, setOwnCommit] = useState("");
  const [ownBusy, setOwnBusy] = useState(false);

  const inferredQuestions = extractLikelyOpenQuestions(synthesis);
  const segments = splitSynthesisSegments(synthesis);

  // Wyciąga akapit "Jeden krok teraz:" z tekstu syntezy (FA2)
  const nextStepText = (() => {
    const marker = /Jeden krok teraz\s*:/i;
    const match = synthesis.match(marker);
    if (!match || match.index == null) return null;
    const after = synthesis.slice(match.index + match[0].length).trimStart();
    // Bierzemy do końca akapitu (podwójny newline) lub max 600 znaków
    const end = after.search(/\n\n/);
    return (end > 0 ? after.slice(0, end) : after.slice(0, 600)).trim() || null;
  })();

  const downloadMd = useCallback(async () => {
    if (debateId != null) {
      const base = getApiBase();
      const url = `${base}/debate/${debateId}/export.md`;
      try {
        const res = await fetch(url, { headers: { ...getApiAuthHeaders() } });
        if (res.ok) {
          const text = await res.text();
          const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
          const u = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = u;
          a.download = `architekt-debate-${debateId}.md`;
          a.click();
          URL.revokeObjectURL(u);
          return;
        }
      } catch {
        /* fallback poniżej */
      }
    }
    const md = synthesisToMarkdown(synthesisStructured, synthesis);
    const blob = new Blob([md], { type: "text/markdown;charset=utf-8" });
    const u = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = u;
    a.download = `synteza-rady-${debateId ?? "draft"}.md`;
    a.click();
    URL.revokeObjectURL(u);
  }, [synthesis, synthesisStructured, debateId]);

  const downloadPdf = useCallback(async () => {
    if (debateId == null) return;
    const base = getApiBase();
    const url = `${base}/debate/${debateId}/export.pdf`;
    try {
      const res = await fetch(url, { headers: { ...getApiAuthHeaders() } });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const u = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = u;
      a.download = `architekt-debate-${debateId}.pdf`;
      a.click();
      URL.revokeObjectURL(u);
    } catch {
      /* ignore — użytkownik może użyć druku */
    }
  }, [debateId]);

  const printPdf = useCallback(() => {
    window.print();
  }, []);

  async function handleContinueSubmit(e: FormEvent) {
    e.preventDefault();
    if (!onContinueThread) return;
    const words = followUp.trim().split(/\s+/).filter(Boolean);
    if (words.length < 5) {
      setCommitErr(t("syez.continue.min_words"));
      return;
    }
    setCommitErr(null);
    setContinuing(true);
    try {
      await onContinueThread(followUp.trim());
      setFollowUp("");
    } catch (err) {
      setCommitErr(err instanceof Error ? err.message : t("syez.continue.error"));
    } finally {
      setContinuing(false);
    }
  }

  async function handleOwnCommit(e: FormEvent) {
    e.preventDefault();
    if (!onCommitStep || !debateId) {
      setCommitErr(t("syez.commit.no_debate"));
      return;
    }
    const txt = ownCommit.trim();
    if (txt.length < 3) {
      setCommitErr(t("syez.force_commit.min"));
      return;
    }
    setCommitErr(null);
    setOwnBusy(true);
    try {
      await onCommitStep(txt, undefined, undefined);
      setOwnCommit("");
    } catch (e) {
      setCommitErr(e instanceof Error ? e.message : t("syez.commit.error_fallback"));
    } finally {
      setOwnBusy(false);
    }
  }

  async function handleCommit(idx: number, step: string, due?: string) {
    if (!onCommitStep || !debateId) {
      setCommitErr(t("syez.commit.no_debate"));
      return;
    }
    setCommitErr(null);
    setCommitting(idx);
    try {
      await onCommitStep(`${t("syez.commit.prefix")}: ${step}`, due, undefined);
    } catch (e) {
      setCommitErr(e instanceof Error ? e.message : t("syez.commit.error_fallback"));
    } finally {
      setCommitting(null);
    }
  }

  const structured = synthesisStructured;

  return (
    <div
      id="syez-export-root"
      className={`
        rounded-xl border-2 p-5 transition-all duration-500 sticky bottom-4 z-20
        ${isActive
          ? "border-teal shadow-[0_0_20px_rgba(20,184,166,0.1)] bg-teal/5"
          : "border-white/10 bg-white/[0.02]"
        }
      `}
    >
      <div className="flex flex-wrap items-start gap-3 mb-4">
        <div className="flex items-center gap-3 flex-1 min-w-[200px]">
          <div className="w-9 h-9 rounded-full bg-teal/20 border border-teal/40 flex items-center justify-center text-[13px] font-medium text-teal flex-shrink-0">
            SY
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[15px] font-medium text-white">Syez</span>
              <span className="text-[10px] px-2 py-[2px] rounded-full bg-teal/20 text-teal border border-teal/30">
                {t("syez.mirror")}
              </span>
              {debateId != null && (
                <span className="text-[10px] text-white/35 font-mono">#{debateId}</span>
              )}
              {debateCost != null && debateCost > 0 && (
                <span className="text-[10px] text-white/30 font-mono" title="Koszt wywołań API tej debaty">
                  {t("syez.debate_cost")}{(debateCost * 0.92).toFixed(3)}{t("syez.debate_cost_eur")}
                </span>
              )}
              {isSynthesizing && (
                <span className="flex gap-[3px] items-center ml-1">
                  {[0, 1, 2].map((i) => (
                    <span
                      key={i}
                      className="w-[4px] h-[4px] rounded-full bg-teal animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }}
                    />
                  ))}
                </span>
              )}
            </div>
            <div className="text-[11px] text-white/40">
              {!isActive && !isAgents && t("syez.status.waiting_council")}
              {isAgents && t("syez.status.gathering")}
              {isSynthesizing && t("syez.status.integrating")}
              {isDone && t("syez.status.done")}
            </div>
          </div>
        </div>

        {isActive && (
          <div className="flex gap-2 no-print">
            <button
              type="button"
              onClick={downloadMd}
              className="text-[11px] px-3 py-1.5 rounded-lg border border-white/15 bg-white/[0.04] hover:border-teal/40 hover:bg-teal/10 transition-colors"
            >
              {t("syez.btn.export_md")}
            </button>
            <button
              type="button"
              onClick={downloadPdf}
              className="text-[11px] px-3 py-1.5 rounded-lg border border-white/15 bg-white/[0.04] hover:border-teal/40 hover:bg-teal/10 transition-colors"
            >
              {t("syez.btn.download_pdf")}
            </button>
            <button
              type="button"
              onClick={printPdf}
              className="text-[11px] px-3 py-1.5 rounded-lg border border-white/15 bg-white/[0.04] hover:border-teal/40 hover:bg-teal/10 transition-colors"
            >
              {t("syez.btn.print_pdf")}
            </button>
          </div>
        )}
      </div>

      {commitErr && (
        <p className="text-[12px] text-red-400 mb-3">{commitErr}</p>
      )}

      {lastCommitmentEcho && isDone && (
        <div className="mb-4 rounded-lg border border-red-500/25 bg-red-950/20 px-3 py-2 text-[11px] text-red-100/90">
          <span className="text-red-300/90 font-medium">72h · </span>
          {String(lastCommitmentEcho.text ?? "")}
        </div>
      )}

      {structured && isActive && (
        <div className="space-y-6 mb-6 border-t border-white/[0.06] pt-5">
          {structured.insights_per_agent && structured.insights_per_agent.length > 0 && (
            <section>
              <h3 className="text-[11px] uppercase tracking-widest text-white/35 mb-3">
                {t("syez.section.insights")}
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {structured.insights_per_agent.map((row, i) => (
                  <div
                    key={`${row.agent}-${i}`}
                    className="rounded-lg border border-white/[0.07] bg-white/[0.02] px-3 py-2"
                  >
                    <div className="text-[11px] text-teal/85 font-medium mb-1">{row.agent}</div>
                    <p className="text-[12px] text-white/70 leading-snug">{row.insight}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {structured.tensions && structured.tensions.length > 0 && (
            <section>
              <h3 className="text-[11px] uppercase tracking-widest text-white/35 mb-3">
                {t("syez.section.tensions")}
              </h3>
              <TensionBars tensions={structured.tensions} />
            </section>
          )}

          {structured.recommendations && structured.recommendations.length > 0 && (
            <section>
              <h3 className="text-[11px] uppercase tracking-widest text-white/35 mb-2">
                {t("syez.section.recommendations")}
              </h3>
              <ol className="list-decimal list-inside space-y-1 text-[13px] text-white/75">
                {structured.recommendations.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ol>
            </section>
          )}

          {structured.open_questions && structured.open_questions.length > 0 && (
            <section>
              <h3 className="text-[11px] uppercase tracking-widest text-white/35 mb-2">
                {t("syez.section.open_questions")}
              </h3>
              <ul className="space-y-2">
                {structured.open_questions.map((q, i) => (
                  <li
                    key={i}
                    className="text-[13px] text-amber-100/90 bg-amber-500/[0.07] border border-amber-500/20 rounded-lg px-3 py-2"
                  >
                    {q}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {structured.action_steps && structured.action_steps.length > 0 && (
            <section>
              <h3 className="text-[11px] uppercase tracking-widest text-white/35 mb-2">
                {t("syez.section.action_steps")}
              </h3>
              <ul className="space-y-2">
                {structured.action_steps.map((a, idx) => (
                  <li
                    key={idx}
                    className="flex flex-col sm:flex-row sm:items-center gap-3 text-[13px] text-white/78 border border-white/[0.06] rounded-lg px-3 py-2"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="text-teal/55 mr-1 select-none">●</span>
                      <span>
                        {a.step}
                        {a.due && (
                          <span className="block text-[11px] text-teal/75 mt-1">
                            {t("syez.action.due")}: {a.due}
                            {a.priority && ` · ${t("syez.action.priority")}: ${a.priority}`}
                          </span>
                        )}
                      </span>
                    </div>
                    <button
                      type="button"
                      disabled={committing === idx || !debateId}
                      onClick={() => void handleCommit(idx, a.step, a.due)}
                      className="no-print shrink-0 text-[11px] px-3 py-1.5 rounded-lg bg-teal/15 border border-teal/35 text-teal hover:bg-teal/25 disabled:opacity-35 disabled:cursor-not-allowed transition-colors"
                    >
                      {committing === idx ? t("syez.btn.committing") : t("syez.btn.commit")}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}

      <div className="border-l-2 border-teal/40 pl-4 space-y-4">
        {!isActive && (
          <p className="text-[12px] text-white/20 italic">
            {t("syez.empty_placeholder")}
          </p>
        )}
        {isActive && (
          <div className="space-y-4">
            {inferredQuestions.length > 0 && (
              <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.06] px-3 py-3">
                <div className="text-[10px] uppercase tracking-widest text-amber-200/55 mb-2">
                  {t("syez.detected_questions")}
                </div>
                <ul className="space-y-2">
                  {inferredQuestions.map((q, i) => (
                    <li key={i} className="text-[12px] text-amber-50/95 leading-snug">
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {isDone && nextStepText && (
              <div className="rounded-lg border border-teal/35 bg-teal/[0.07] px-4 py-3">
                <div className="text-[10px] uppercase tracking-widest text-teal/70 mb-1.5">
                  Jeden krok teraz
                </div>
                <p className="text-[13px] text-white/90 leading-snug">{nextStepText}</p>
              </div>
            )}
            <div className="text-[13px] text-white/80 leading-relaxed">
              {segments.map((seg, idx) =>
                seg.kind === "mermaid" ? (
                  <MermaidBlock key={`m-${idx}`} chart={seg.value} />
                ) : (
                  <div key={`t-${idx}`} className="whitespace-pre-wrap">
                    {seg.value}
                  </div>
                ),
              )}
              {isSynthesizing && (
                <span className="inline-block w-[2px] h-[13px] bg-teal ml-[2px] align-text-bottom animate-pulse" />
              )}
            </div>
          </div>
        )}
      </div>

      {isDone && onCommitStep && debateId != null && (
        <form
          onSubmit={(e) => void handleOwnCommit(e)}
          className="no-print mt-5 pt-5 border-t border-red-500/20 space-y-2"
        >
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <label className="block text-[11px] uppercase tracking-widest text-red-300/80">
              {t("syez.force_commit.title")}
            </label>
            {debateMode === "schematy" && (
              <span className="text-[9px] px-2 py-0.5 rounded-full border border-amber-500/35 text-amber-200/90">
                72h
              </span>
            )}
          </div>
          <p className="text-[10px] text-white/40 leading-snug">{t("syez.force_commit.lead")}</p>
          <textarea
            value={ownCommit}
            onChange={(e) => setOwnCommit(e.target.value)}
            rows={3}
            placeholder={t("syez.force_commit.placeholder")}
            className="w-full rounded-lg bg-black/40 border border-red-500/20 px-3 py-2 text-[13px] text-white/90 placeholder:text-white/25 focus:outline-none focus:border-red-400/50 resize-y min-h-[72px]"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={ownBusy || status !== "done"}
              className="text-[12px] px-4 py-2 rounded-lg bg-red-900/35 border border-red-500/45 text-red-100 hover:bg-red-900/50 disabled:opacity-35 disabled:cursor-not-allowed transition-colors"
            >
              {ownBusy ? t("syez.btn.committing") : t("syez.force_commit.btn")}
            </button>
          </div>
        </form>
      )}

      {isDone && onContinueThread && debateId != null && (
        <form
          onSubmit={(e) => void handleContinueSubmit(e)}
          className="no-print mt-5 pt-5 border-t border-white/[0.07] space-y-2"
        >
          <label className="block text-[11px] uppercase tracking-widest text-white/35">
            {t("syez.continue.label")}
          </label>
          <textarea
            value={followUp}
            onChange={(e) => setFollowUp(e.target.value)}
            rows={3}
            placeholder={t("syez.continue.placeholder")}
            className="w-full rounded-lg bg-black/35 border border-white/15 px-3 py-2 text-[13px] text-white/90 placeholder:text-white/25 focus:outline-none focus:border-teal/50 resize-y min-h-[72px]"
          />
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={continuing || status !== "done"}
              className="text-[12px] px-4 py-2 rounded-lg bg-teal/20 border border-teal/45 text-teal hover:bg-teal/30 disabled:opacity-35 disabled:cursor-not-allowed transition-colors"
            >
              {continuing ? t("syez.continue.btn_starting") : t("syez.continue.btn")}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
