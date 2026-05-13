import { useCallback, useState } from "react";
import { LocalSetupModal } from "@/components/LocalSetupModal";
import { useDebate } from "@/hooks/useDebate";
import { AgentCard } from "@/components/AgentCard";
import { SyezPanel } from "@/components/SyezPanel";
import { BriefForm } from "@/components/BriefForm";
import { ModeSidebar } from "@/components/ModeSidebar";
import { TensionMeter } from "@/components/TensionMeter";
import { CommitmentsTimeline } from "@/components/CommitmentsTimeline";
import { DebateHistory } from "@/components/DebateHistory";
import { ProductManifest } from "@/components/ProductManifest";
import { DreamsPanel } from "@/components/DreamsPanel";
import { useLang } from "@/lib/i18n";
import type { Brief } from "@/types/debate";

const LS_SETUP_DONE = "aw_setup_v2_done";

function readSetupDismissed(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return localStorage.getItem(LS_SETUP_DONE) === "1";
  } catch {
    return false;
  }
}

export default function App() {
  const { lang, setLang, t } = useLang();
  const {
    state,
    startDebate,
    continueDebateThread,
    reset,
    submitCommitment,
    loadHistoricalDebate,
  } = useDebate();
  const [mode, setMode] = useState<Brief["mode"]>("pelna");
  const [aggressiveSchema, setAggressiveSchema] = useState(false);
  const [setupNagDismissed, setSetupNagDismissed] = useState(() =>
    readSetupDismissed(),
  );
  const [setupOpen, setSetupOpen] = useState(() => !readSetupDismissed());

  const dismissSetupStartup = useCallback(() => {
    try {
      localStorage.setItem(LS_SETUP_DONE, "1");
    } catch {
      /* ignore */
    }
    setSetupNagDismissed(true);
    setSetupOpen(false);
  }, []);

  const isActive =
    state.status === "agents_speaking" || state.status === "synthesizing";
  const agentList = Object.values(state.agents);

  const STATUS_LABEL: Record<string, string> = {
    idle: t("app.status.idle"),
    agents_speaking: t("app.status.agents_speaking"),
    synthesizing: t("app.status.synthesizing"),
    done: t("app.status.done"),
    error: t("app.status.error"),
  };

  const handleCommit = useCallback(
    async (text: string, due?: string, followUp?: string) => {
      await submitCommitment(
        state.debateId,
        text,
        due,
        followUp,
        state.project?.id,
      );
    },
    [submitCommitment, state.debateId, state.project?.id],
  );

  const handleStart = useCallback(
    (brief: Brief) => {
      void startDebate({ ...brief, language: lang });
    },
    [startDebate, lang],
  );

  return (
    <div className="min-h-screen bg-navy text-white font-sans flex">
      <LocalSetupModal
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        showStartupDismiss={!setupNagDismissed}
        onDismissStartup={dismissSetupStartup}
      />
      <aside className="no-print w-[248px] shrink-0 border-r border-white/[0.06] px-4 py-6 hidden lg:flex flex-col">
        <div className="mb-2 px-2">
          <span className="text-[11px] uppercase tracking-widest text-white/30">
            {t("app.brand")}
          </span>
        </div>
        <ModeSidebar selected={mode} onChange={setMode} disabled={isActive} />
        <DreamsPanel disabled={isActive} />
        <DebateHistory onSelect={loadHistoricalDebate} disabled={isActive} />
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="border-b border-white/[0.06] px-6 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[18px] font-medium truncate">
              {t("app.title.supervisory")}{" "}
              <span className="text-teal">{t("app.title.council")}</span>
            </span>
            <span className="text-[10px] px-2 py-[2px] rounded-full bg-white/5 border border-white/10 text-white/40 shrink-0">
              v3.3 / spec v1.1
            </span>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span
              className={`text-[12px] px-3 py-1 rounded-full border ${
                isActive
                  ? "bg-teal/10 border-teal/30 text-teal"
                  : state.status === "done"
                  ? "bg-green-900/20 border-green-500/30 text-green-400"
                  : state.status === "error"
                  ? "bg-red-900/20 border-red-500/30 text-red-400"
                  : "bg-white/5 border-white/10 text-white/40"
              }`}
            >
              {STATUS_LABEL[state.status] ?? state.status}
            </span>

            <button
              type="button"
              onClick={() => setSetupOpen(true)}
              className="no-print text-[11px] px-2 py-1 rounded-full border border-white/12 text-white/45 hover:text-white/80 hover:border-white/25 transition-colors"
            >
              {t("setup.btn_connection")}
            </button>

            <button
              type="button"
              onClick={() => setLang(lang === "pl" ? "en" : "pl")}
              title={t("app.lang.toggle_tooltip")}
              aria-label={t("app.lang.toggle_tooltip")}
              className="no-print inline-flex items-center gap-[3px] text-[11px] font-mono px-2 py-1 rounded-full border border-white/15 bg-white/[0.04] hover:border-teal/40 hover:bg-teal/10 transition-colors"
            >
              <span
                className={
                  lang === "pl" ? "text-teal" : "text-white/35"
                }
              >
                PL
              </span>
              <span className="text-white/20">/</span>
              <span
                className={
                  lang === "en" ? "text-teal" : "text-white/35"
                }
              >
                EN
              </span>
            </button>

            {state.status !== "idle" && (
              <button
                type="button"
                onClick={reset}
                disabled={isActive}
                className="no-print text-[12px] text-white/30 hover:text-white/60 transition-colors disabled:cursor-not-allowed"
              >
                {t("app.btn.reset")}
              </button>
            )}
          </div>
        </header>

        {state.budgetWarning && (
          <div className="no-print mx-6 mt-4 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-[13px] text-amber-100/95">
            {state.budgetWarning}
          </div>
        )}

        <main className="max-w-5xl mx-auto px-6 py-8 space-y-8 w-full pb-24">
          <section className="lg:hidden no-print mb-6 space-y-4">
            <p className="text-[11px] uppercase tracking-widest text-white/35">
              {t("app.mobile_mode_label")}
            </p>
            <ModeSidebar
              selected={mode}
              onChange={setMode}
              disabled={isActive}
            />
          </section>

          <section className="space-y-4">
            <ProductManifest />
            <BriefForm
              onSubmit={handleStart}
              disabled={isActive}
              selectedMode={mode}
              aggressiveSchema={aggressiveSchema}
              onAggressiveSchemaChange={setAggressiveSchema}
              onModeChange={setMode}
            />
          </section>

          {state.status === "error" && (
            <div className="rounded-lg border border-red-500/30 bg-red-900/10 px-4 py-3 text-[13px] text-red-400">
              {state.error ?? t("app.error.unknown")}
            </div>
          )}

          {agentList.length > 0 && (
            <section>
              <h2 className="text-[11px] uppercase tracking-widest text-white/30 mb-4">
                {t("app.section.council")}
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {agentList.map((agent) => (
                  <AgentCard key={agent.name} agent={agent} />
                ))}
              </div>
            </section>
          )}

          {(state.liveTensions?.length ?? 0) > 0 && (
            <TensionMeter pairs={state.liveTensions ?? []} />
          )}

          {(agentList.length > 0 ||
            state.status === "synthesizing" ||
            state.status === "done") && (
            <section>
              <h2 className="text-[11px] uppercase tracking-widest text-white/30 mb-4">
                {t("app.section.synthesis")}
              </h2>
              <SyezPanel
                synthesis={state.synthesis}
                synthesisStructured={state.synthesisStructured}
                status={state.status}
                debateId={state.debateId}
                debateCost={state.debateCost}
                debateMode={state.debateMode}
                lastCommitmentEcho={state.lastCommitmentEcho}
                onContinueThread={
                  state.debateId
                    ? (followUp) =>
                        continueDebateThread({
                          previous_debate_id: state.debateId!,
                          follow_up: followUp,
                        })
                    : undefined
                }
                onCommitStep={handleCommit}
              />
              {state.status === "done" && state.project?.id != null && (
                <CommitmentsTimeline projectId={state.project.id} />
              )}
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
