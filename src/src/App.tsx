import { useCallback, useEffect, useState } from "react";
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
import {
  OnboardingPanel,
  DailyRitualPanel,
} from "@/components/PersonalRitualPanels";
import { FragmentCompass } from "@/components/FragmentCompass";
import { ActiveProjectLimitModal, type ActiveProjectInfo } from "@/components/ActiveProjectLimitModal";
import { DreamWizard } from "@/components/DreamWizard";
import { NotificationsPanel } from "@/components/NotificationsPanel";
import { IntegrationsModal } from "@/components/IntegrationsModal";
import { OfflineBanner, addToOfflineQueue } from "@/components/OfflineBanner";
import {
  LoginScreen,
  getStoredJwt,
  setStoredJwt,
  getStoredUserDisplay,
} from "@/components/LoginScreen";
import { useLang } from "@/lib/i18n";
import {
  getCouncilMode,
  setCouncilMode,
  COUNCIL_MODE_EVENT,
} from "@/config/product";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import {
  clearDemoSession,
  fetchDemoStatus,
  fetchEditionDemoConfig,
  isDemoSession,
  type DemoPublicConfig,
  type DemoStatus,
} from "@/lib/demoConfig";
import type { Brief } from "@/types/debate";

const LS_SETUP_DONE = "aw_setup_v2_done";

function _jwtEnabled(): boolean {
  try {
    return localStorage.getItem("aw_jwt_enabled") === "1";
  } catch {
    return false;
  }
}

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
  const [councilMode, setCouncilModeState] = useState(() => getCouncilMode());
  const [backendMode, setBackendMode] = useState<string | null>(null);
  const [dreamWizardOpen, setDreamWizardOpen] = useState(false);
  const [integrationsOpen, setIntegrationsOpen] = useState(false);
  const [authenticated, setAuthenticated] = useState(() => {
    const jwt = getStoredJwt();
    return jwt !== null || !_jwtEnabled();
  });
  const [demoPublicConfig, setDemoPublicConfig] =
    useState<DemoPublicConfig | null>(null);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const inDemo = isDemoSession();

  // Register SW for offline-first
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetchEditionDemoConfig().then((cfg) => {
      if (!cancelled) setDemoPublicConfig(cfg);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const refreshDemoStatus = useCallback(async () => {
    if (!isDemoSession()) {
      setDemoStatus(null);
      return;
    }
    const st = await fetchDemoStatus();
    setDemoStatus(st);
  }, []);

  useEffect(() => {
    if (!authenticated || !inDemo) return;
    void refreshDemoStatus();
  }, [authenticated, inDemo, refreshDemoStatus, state.status, state.debateId]);

  useEffect(() => {
    if (!inDemo || !demoPublicConfig) return;
    const allowed = demoPublicConfig.allowed_modes;
    if (allowed.length > 0 && (!mode || !allowed.includes(mode))) {
      setMode(allowed[0] as Brief["mode"]);
    }
  }, [inDemo, demoPublicConfig, mode]);

  const toggleCouncilMode = useCallback(() => {
    const next = councilMode === "personal" ? "fa2" : "personal";
    setCouncilMode(next);
    setCouncilModeState(next);
    // bez reloadu — komponenty (ModeSidebar, DreamsPanel) re-renderują się
    // dzięki kluczowi `key={councilMode}` na drzewie
  }, [councilMode]);

  // sprawdź tryb backendu (do banera niespójności)
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${getApiBase()}/health`, {
          headers: { ...getApiAuthHeaders() },
        });
        if (!r.ok) return;
        const j = await r.json();
        if (!cancelled) {
          const hf = j?.fa2_via_header === true;
          if (hf) {
            setBackendMode(councilMode === "fa2" ? "fa2" : "personal");
          } else {
            const m = typeof j?.council_mode === "string" ? j.council_mode : null;
            setBackendMode(m);
          }
        }
      } catch {
        /* offline / niedostępne — baner pominięty */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [councilMode]);

  // sync między zakładkami / komponentami
  useEffect(() => {
    const onChange = () => setCouncilModeState(getCouncilMode());
    window.addEventListener(COUNCIL_MODE_EVENT, onChange);
    window.addEventListener("storage", onChange);
    return () => {
      window.removeEventListener(COUNCIL_MODE_EVENT, onChange);
      window.removeEventListener("storage", onChange);
    };
  }, []);

  // baner gdy frontend ≠ backend
  const backendDisplay =
    backendMode === "fa2" ? "fa2" : backendMode ? "personal" : null;
  const modeMismatch =
    backendDisplay !== null && backendDisplay !== councilMode;

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
      if (!navigator.onLine) {
        addToOfflineQueue({ ...brief, language: lang });
        return;
      }
      void startDebate({ ...brief, language: lang });
    },
    [startDebate, lang],
  );

  // Dream Wizard auto-open when switching to marzen mode
  useEffect(() => {
    if (mode === "marzen" && state.status === "idle") {
      setDreamWizardOpen(true);
    }
  }, [mode, state.status]);

  if (!authenticated) {
    return (
      <LoginScreen
        onAuthenticated={() => setAuthenticated(true)}
        demoConfig={demoPublicConfig}
      />
    );
  }

  const demoRemaining = demoStatus?.debates_remaining;
  const demoExhausted =
    inDemo && typeof demoRemaining === "number" && demoRemaining <= 0;
  const maxBriefChars = inDemo
    ? (demoPublicConfig?.max_brief_chars ?? 800)
    : 8000;
  const allowedDemoModes = inDemo
    ? demoPublicConfig?.allowed_modes
    : undefined;

  return (
    <div
      key={councilMode}
      className="min-h-screen bg-navy text-white font-sans flex"
    >
      <LocalSetupModal
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        showStartupDismiss={!setupNagDismissed}
        onDismissStartup={dismissSetupStartup}
      />
      <IntegrationsModal
        open={integrationsOpen}
        onClose={() => setIntegrationsOpen(false)}
      />
      {councilMode === "personal" && <OnboardingPanel />}
      {/* AKSJOMAT 0 — kompas Fragmentu. Stale widoczny w trybie personal,
          jako delikatne przypomnienie że to nie jest todo, tylko postawa. */}
      {councilMode === "personal" && (
        <div className="fixed bottom-4 right-4 z-40 max-w-[320px] no-print">
          <FragmentCompass compact />
        </div>
      )}
      {/* AKSJOMAT 2 — konfrontacja gdy backend zwraca 409 active_project_limit.
          Zamiast suchego błędu: pełen dialog z aktywnymi projektami i trzema
          świadomymi opcjami (kończę / archiwizuję / rezygnuję). */}
      {state.auditViolation?.kind === "active_project_limit" && (
        <ActiveProjectLimitModal
          open
          limit={Number(state.auditViolation.details?.limit ?? 1)}
          activeProjects={(state.auditViolation.details?.active_projects as ActiveProjectInfo[]) ?? []}
          onFinish={(pid) => {
            // TODO (osobny PR): otwarcie widoku functionality_checklist dla #pid.
            // Tutaj zamykamy modal — user kontynuuje ręcznie w sekcji projektów.
            console.info("[AKSJOMAT 2] użytkownik kończy projekt:", pid);
            window.location.hash = `#project=${pid}`;
          }}
          onArchive={(pid) => {
            console.info("[AKSJOMAT 2] użytkownik archiwizuje świadomie:", pid);
            window.location.hash = `#archive=${pid}`;
          }}
          onCancel={() => {
            // Czyścimy violation — user świadomie zrezygnował z nowego.
            // (Reset stanu robi useDebate przy nowym briefie.)
            window.location.reload();
          }}
        />
      )}
      {dreamWizardOpen && (
        <DreamWizard
          onSubmit={(b) => {
            setDreamWizardOpen(false);
            handleStart(b);
          }}
          disabled={isActive}
          onClose={() => setDreamWizardOpen(false)}
        />
      )}
      <aside className="no-print w-[248px] shrink-0 border-r border-white/[0.06] px-4 py-6 hidden lg:flex flex-col">
        <div className="mb-2 px-2">
          <span className="text-[11px] uppercase tracking-widest text-white/30">
            {t("app.brand")}
          </span>
        </div>
        <ModeSidebar
          selected={mode}
          onChange={setMode}
          disabled={isActive}
          allowedModes={allowedDemoModes}
        />
        <DreamsPanel disabled={isActive || inDemo} />
        {councilMode === "personal" && !inDemo && (
          <div className="mt-4">
            <DailyRitualPanel />
          </div>
        )}
        {councilMode === "personal" && <NotificationsPanel />}
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

            {!inDemo && (
              <button
                type="button"
                onClick={toggleCouncilMode}
                disabled={isActive}
                title={
                  councilMode === "personal"
                    ? "Przełącz na wersję biznesową (FA2)"
                    : "Przełącz na wersję osobistą (Mój Świat)"
                }
                className={`no-print inline-flex items-center gap-[6px] text-[11px] font-mono px-3 py-1 rounded-full border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                  councilMode === "fa2"
                    ? "border-amber-400/40 bg-amber-400/10 text-amber-200 hover:border-amber-300/60"
                    : "border-teal/40 bg-teal/10 text-teal hover:border-teal/60"
                }`}
              >
                <span
                  className={
                    councilMode === "personal" ? "text-teal" : "text-white/35"
                  }
                >
                  Osobista
                </span>
                <span className="text-white/20">/</span>
                <span
                  className={
                    councilMode === "fa2" ? "text-amber-300" : "text-white/35"
                  }
                >
                  Biznesowa
                </span>
              </button>
            )}

            <button
              type="button"
              onClick={() => setSetupOpen(true)}
              className="no-print text-[11px] px-2 py-1 rounded-full border border-white/12 text-white/45 hover:text-white/80 hover:border-white/25 transition-colors"
            >
              {t("setup.btn_connection")}
            </button>

            {!inDemo && (
              <button
                type="button"
                onClick={() => setIntegrationsOpen(true)}
                className="no-print text-[11px] px-2 py-1 rounded-full border border-white/12 text-white/45 hover:text-white/80 hover:border-white/25 transition-colors"
              >
                {t("integrations.title")}
              </button>
            )}

            {getStoredJwt() && (
              <button
                type="button"
                onClick={() => {
                  if (inDemo) clearDemoSession();
                  else setStoredJwt(null);
                  setAuthenticated(false);
                  setDemoStatus(null);
                }}
                className="no-print text-[11px] px-2 py-1 rounded-full border border-white/12 text-white/45 hover:text-white/80 hover:border-white/25 transition-colors"
                title={getStoredUserDisplay() ?? undefined}
              >
                {inDemo ? t("demo.new_session") : t("login.logout")}
              </button>
            )}

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

        {inDemo && (
          <div
            role="status"
            className={`no-print mx-6 mt-4 rounded-lg border px-4 py-3 text-[13px] ${
              demoExhausted
                ? "border-red-500/40 bg-red-900/15 text-red-200/95"
                : "border-amber-400/35 bg-amber-400/10 text-amber-100/95"
            }`}
          >
            {demoExhausted
              ? t("demo.banner_exhausted")
              : t("demo.banner").replace(
                  "{n}",
                  String(demoRemaining ?? "—"),
                )}
          </div>
        )}

        {state.budgetWarning && (
          <div className="no-print mx-6 mt-4 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-[13px] text-amber-100/95">
            {state.budgetWarning}
          </div>
        )}

        <OfflineBanner
          onReplayBrief={(b) => handleStart(b as unknown as Brief)}
        />

        {modeMismatch && (
          <div
            role="alert"
            className="no-print mx-6 mt-4 rounded-lg border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-[13px] text-rose-100/95"
          >
            Niespójność trybów: UI pokazuje{" "}
            <strong>
              {councilMode === "fa2" ? "Biznesowa (FA2)" : "Osobista (Mój Świat)"}
            </strong>
            , ale backend działa w trybie{" "}
            <strong>
              {backendDisplay === "fa2"
                ? "Biznesowa (FA2)"
                : "Osobista (Mój Świat)"}
            </strong>
            . Debata idzie z nagłówkiem <code>X-Council-Mode</code> — przełącz UI
            albo dopasuj <code>AW_COUNCIL_MODE</code> / proxy, jeśli nagłówki są
            obcinane.
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
              allowedModes={allowedDemoModes}
            />
          </section>

          <section className="space-y-4">
            <ProductManifest />
            <BriefForm
              onSubmit={handleStart}
              disabled={isActive || demoExhausted}
              selectedMode={mode}
              aggressiveSchema={aggressiveSchema}
              onAggressiveSchemaChange={setAggressiveSchema}
              onModeChange={setMode}
              maxDescriptionLen={maxBriefChars}
              allowedModes={allowedDemoModes}
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
