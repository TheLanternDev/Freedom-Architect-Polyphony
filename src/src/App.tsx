import { useCallback, useEffect, useState } from "react";
import { Clock, Eye, Flag, MessageCircle, Settings } from "lucide-react";
import { LocalSetupModal } from "@/components/LocalSetupModal";
import { useDebate } from "@/hooks/useDebate";
import { CouncilCircle } from "@/components/CouncilCircle";
import { SyezPanel } from "@/components/SyezPanel";
import { PriorTurnView } from "@/components/PriorTurnView";
import { BriefForm } from "@/components/BriefForm";
import { CommitmentsTimeline } from "@/components/CommitmentsTimeline";
import { DebateCommitments } from "@/components/DebateCommitments";
import { FadeIn } from "@/components/ui/FadeIn";
import { Icon } from "@/components/ui/Icon";
import { SectionDivider } from "@/components/ui/SectionDivider";
import { OnboardingPanel, DailyRitualPanel } from "@/components/PersonalRitualPanels";
import { MojObrazPanel } from "@/components/MojObrazPanel";
import { DreamsPanel } from "@/components/DreamsPanel";
import { DebateHistory } from "@/components/DebateHistory";
import { NotificationsPanel } from "@/components/NotificationsPanel";
import { ActiveProjectLimitModal, type ActiveProjectInfo } from "@/components/ActiveProjectLimitModal";
import { DreamWizard } from "@/components/DreamWizard";
import { IntegrationsModal } from "@/components/IntegrationsModal";
import { FeedbackPanel } from "@/components/FeedbackPanel";
import { clearIntegrationStatusCache } from "@/components/CommitmentExportButtons";
import { WorkspaceHeader } from "@/components/WorkspaceHeader";
import { OfflineBanner, addToOfflineQueue } from "@/components/OfflineBanner";
import {
  LoginScreen,
  getStoredJwt,
  setStoredJwt,
} from "@/components/LoginScreen";
import { DeviceLockScreen } from "@/components/DeviceLockScreen";
import { useLang } from "@/lib/i18n";
import {
  getCouncilMode,
  setCouncilMode,
  COUNCIL_MODE_EVENT,
} from "@/config/product";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { loadLlmKey } from "@/lib/llmKeyStorage";
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
  const [sidePanel, setSidePanel] = useState<"dreams" | "history" | "notifications" | "obraz" | null>(null);
  const [councilMode, setCouncilModeState] = useState(() => getCouncilMode());
  const [backendMode, setBackendMode] = useState<string | null>(null);
  const [dreamWizardOpen, setDreamWizardOpen] = useState(false);
  const [integrationsOpen, setIntegrationsOpen] = useState(false);
  // Feedback soft-launchu — opóźniony trigger po domknięciu debaty (AX2 pierwszeństwo:
  // commit/kontynuacja/nowa debata w pierwszych ~90s), max 1× / 24h (7 dni po submit).
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackForDebate, setFeedbackForDebate] = useState<number | null>(null);

  useEffect(() => {
    void loadLlmKey();
  }, []);

  useEffect(() => {
    if (state.status !== "done" || state.debateId == null) return;
    if (feedbackForDebate === state.debateId) return;
    try {
      const until = Number(localStorage.getItem("aw_feedback_snooze_until") ?? 0);
      if (Number.isFinite(until) && Date.now() < until) return;
    } catch {
      // brak localStorage → pokaż po delayu
    }
    const debateId = state.debateId;
    const timer = window.setTimeout(() => {
      setFeedbackForDebate(debateId);
      setFeedbackOpen(true);
    }, 90_000);
    return () => window.clearTimeout(timer);
  }, [state.status, state.debateId, feedbackForDebate]);
  const [authenticated, setAuthenticated] = useState(() => {
    const jwt = getStoredJwt();
    return jwt !== null || !_jwtEnabled();
  });
  const [demoPublicConfig, setDemoPublicConfig] =
    useState<DemoPublicConfig | null>(null);
  const [demoStatus, setDemoStatus] = useState<DemoStatus | null>(null);
  const inDemo = isDemoSession();

  // Device binding: sprawdź czy instalacja nie jest powiązana z innym
  // komputerem (skopiowany folder). null = jeszcze nie sprawdzono.
  const [deviceLock, setDeviceLock] = useState<{
    locked: boolean;
    fpCurrent?: string | null;
    fpSealed?: string | null;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${getApiBase()}/device/status`);
        if (!r.ok) {
          // Backend bez device-routera (starsza wersja) → nie blokuj.
          if (!cancelled) setDeviceLock({ locked: false });
          return;
        }
        const j = await r.json();
        if (!cancelled) {
          setDeviceLock({
            locked: j?.locked === true,
            fpCurrent: j?.fingerprint_current ?? null,
            fpSealed: j?.fingerprint_sealed ?? null,
          });
        }
      } catch {
        // Offline / brak backendu — nie blokuj UI z powodu device-checka.
        if (!cancelled) setDeviceLock({ locked: false });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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

  const selectCouncilMode = useCallback(
    (next: "personal" | "fa2") => {
      if (next === councilMode) return;
      setCouncilMode(next);
      setCouncilModeState(next);
    },
    [councilMode],
  );

  // sprawdź tryb backendu (do banera niespójności)
  useEffect(() => {
    setBackendMode(null); // reset przy każdej zmianie trybu — eliminuje fałszywy flash
    let cancelled = false;
    (async () => {
      try {
        const r = await fetch(`${getApiBase()}/health`, {
          headers: { ...getApiAuthHeaders() },
        });
        if (!r.ok) return;
        const j = await r.json();
        if (!cancelled) {
          // P1-A5: serwer deklaruje wymóg auth — lokalna flaga `aw_jwt_enabled`
          // przestaje być źródłem prawdy. Gdy backend ma skonfigurowane JWT,
          // a klient nie ma tokenu → wymuś ekran logowania.
          if (j?.auth_required === true) {
            try {
              localStorage.setItem("aw_jwt_enabled", "1");
            } catch {
              /* ignore */
            }
            if (getStoredJwt() === null) {
              setAuthenticated(false);
            }
          }
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
  const showBriefSetup =
    state.status === "idle" &&
    agentList.length === 0 &&
    (state.turns?.length ?? 0) === 0;

  const STATUS_LABEL: Record<string, string> = {
    idle: t("app.status.idle"),
    agents_speaking: t("app.status.agents_speaking"),
    synthesizing: t("app.status.synthesizing"),
    done: t("app.status.done"),
    error: t("app.status.error"),
    safety_halt: t("app.status.safety_halt"),
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
      void startDebate({ ...brief, language: lang }, {
        onNeedLlmKey: () => setSetupOpen(true),
      });
    },
    [startDebate, lang],
  );

  // Dream Wizard auto-open when switching to marzen mode
  useEffect(() => {
    if (mode === "marzen" && state.status === "idle") {
      setDreamWizardOpen(true);
    }
  }, [mode, state.status]);

  // Warstwa 0: blokada urządzenia (przed logowaniem). Pieczęć z innej maszyny
  // = skopiowana instalacja → nie wpuszczamy dalej.
  if (deviceLock?.locked) {
    return (
      <DeviceLockScreen
        fingerprintCurrent={deviceLock.fpCurrent}
        fingerprintSealed={deviceLock.fpSealed}
      />
    );
  }

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
    <div key={councilMode} className="aw-app-shell" data-council-mode={councilMode}>
      <LocalSetupModal
        open={setupOpen}
        onClose={() => setSetupOpen(false)}
        showStartupDismiss={!setupNagDismissed}
        onDismissStartup={dismissSetupStartup}
        inDemo={inDemo}
        onAccountDeleted={() => {
          setAuthenticated(false);
          setSetupOpen(false);
        }}
      />
      <IntegrationsModal
        open={integrationsOpen}
        onClose={() => setIntegrationsOpen(false)}
      />
      <FeedbackPanel
        open={feedbackOpen}
        debateId={feedbackForDebate ?? undefined}
        onClose={(submitted) => {
          setFeedbackOpen(false);
          try {
            const hours = submitted ? 7 * 24 : 24;
            localStorage.setItem(
              "aw_feedback_snooze_until",
              String(Date.now() + hours * 3_600_000),
            );
          } catch {
            // localStorage niedostępny — trudno, pokażemy ponownie
          }
        }}
      />
      {councilMode === "personal" && <OnboardingPanel />}
      {/* AKSJOMAT 0 — kompas Fragmentu wbudowany w BriefForm (Krok 4 redesignu) */}
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
      {/* ── Icon rail — zastępuje 272px sidebar (Krok 1 redesignu) ── */}
      <aside className="no-print w-[52px] shrink-0 border-r border-border bg-[#0A0C14] hidden lg:flex flex-col h-screen sticky top-0 z-10">
        {/* AW brand mark */}
        <div className="shrink-0 h-14 flex items-center justify-center border-b border-border/60">
          <div className="w-8 h-8 rounded-lg bg-gold/10 border border-gold/25 flex items-center justify-center text-[10px] font-semibold text-gold leading-none select-none">
            AW
          </div>
        </div>

        {/* Nav icons */}
        <nav className="flex-1 flex flex-col items-center pt-3 gap-1" aria-label="Nawigacja główna">
          {/* Brief / Debata — zamyka wysuwany panel */}
          <button
            type="button"
            title={t("nav.brief")}
            onClick={() => setSidePanel(null)}
            className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 ${
              showBriefSetup && !sidePanel
                ? "bg-gold/10 text-gold"
                : "text-text-tertiary hover:bg-white/[0.04] hover:text-text-secondary"
            }`}
          >
            <Icon icon={MessageCircle} size="sm" />
          </button>
          {/* Marzenia — wysuwany panel */}
          <button
            type="button"
            title={t("nav.dreams")}
            onClick={() => setSidePanel((p) => p === "dreams" ? null : "dreams")}
            className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 ${
              sidePanel === "dreams"
                ? "bg-gold/10 text-gold"
                : "text-text-tertiary hover:bg-white/[0.04] hover:text-text-secondary"
            }`}
          >
            <Icon icon={Eye} size="sm" />
          </button>
          {/* Powiadomienia / Zobowiązania — wysuwany panel */}
          <button
            type="button"
            title={t("nav.notifications")}
            onClick={() => setSidePanel((p) => p === "notifications" ? null : "notifications")}
            className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 ${
              sidePanel === "notifications"
                ? "bg-gold/10 text-gold"
                : "text-text-tertiary hover:bg-white/[0.04] hover:text-text-secondary"
            }`}
          >
            <Icon icon={Flag} size="sm" />
          </button>
          {/* Historia — wysuwany panel */}
          <button
            type="button"
            title={t("nav.history")}
            onClick={() => setSidePanel((p) => p === "history" ? null : "history")}
            className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 ${
              sidePanel === "history"
                ? "bg-gold/10 text-gold"
                : "text-text-tertiary hover:bg-white/[0.04] hover:text-text-secondary"
            }`}
          >
            <Icon icon={Clock} size="sm" />
          </button>
          {/* Mój obraz — tylko tryb osobisty */}
          {councilMode === "personal" && (
            <button
              type="button"
              title={t("obraz.section")}
              onClick={() => setSidePanel((p) => p === "obraz" ? null : "obraz")}
              className={`w-9 h-9 rounded-lg flex items-center justify-center transition-colors duration-150 ${
                sidePanel === "obraz"
                  ? "bg-gold/10 text-gold"
                  : "text-text-tertiary hover:bg-white/[0.04] hover:text-text-secondary"
              }`}
            >
              <Icon icon={Eye} size="sm" />
            </button>
          )}
        </nav>

        {/* Bottom — settings */}
        <div className="shrink-0 pb-4 flex flex-col items-center border-t border-border/60 pt-3">
          <button
            type="button"
            title={t("nav.settings")}
            onClick={() => setSetupOpen(true)}
            className="w-9 h-9 rounded-lg flex items-center justify-center text-text-tertiary hover:bg-white/[0.04] hover:text-text-secondary transition-colors duration-150"
          >
            <Icon icon={Settings} size="sm" />
          </button>
        </div>
      </aside>

      {/* ── Wysuwany panel kontekstowy — otwierany przyciskami railu ── */}
      {sidePanel && (
        <aside className="no-print w-[240px] shrink-0 border-r border-border bg-surface/60 hidden lg:flex flex-col h-screen sticky top-0 overflow-hidden">
          {/* Header panelu */}
          <div className="shrink-0 h-14 flex items-center justify-between px-4 border-b border-border/80">
            <p className="aw-eyebrow">
              {sidePanel === "dreams" && t("nav.dreams")}
              {sidePanel === "history" && t("nav.history")}
              {sidePanel === "notifications" && t("nav.notifications_short")}
              {sidePanel === "obraz" && t("obraz.section")}
            </p>
            <button
              type="button"
              onClick={() => setSidePanel(null)}
              className="text-text-tertiary hover:text-text-secondary transition-colors text-[18px] leading-none"
              aria-label="Zamknij panel"
            >
              ×
            </button>
          </div>
          {/* Zawartość panelu */}
          <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain aw-scroll px-4 py-4 space-y-4">
            {sidePanel === "dreams" && (
              <>
                <DreamsPanel disabled={isActive || inDemo} />
                {councilMode === "personal" && !inDemo && <DailyRitualPanel />}
              </>
            )}
            {sidePanel === "history" && (
              <DebateHistory onSelect={(id) => { loadHistoricalDebate(id); setSidePanel(null); }} disabled={isActive} />
            )}
            {sidePanel === "notifications" && councilMode === "personal" && (
              <NotificationsPanel />
            )}
            {sidePanel === "notifications" && councilMode !== "personal" && (
              <p className="text-[12px] text-text-tertiary">Powiadomienia dostępne w trybie personal.</p>
            )}
            {sidePanel === "obraz" && <MojObrazPanel />}
          </div>
        </aside>
      )}

      <div className="flex-1 flex flex-col min-w-0">
        <WorkspaceHeader
          status={state.status}
          statusLabel={STATUS_LABEL[state.status] ?? state.status}
          pendingMsg={state.pendingMsg}
          showPending={!!(state.pendingMsg && agentList.length === 0)}
          councilMode={councilMode}
          inDemo={inDemo}
          lang={lang}
          isActive={isActive}
          authenticatedJwt={!!getStoredJwt()}
          onCouncilModeSelect={selectCouncilMode}
          onOpenSetup={() => setSetupOpen(true)}
          onOpenIntegrations={() => setIntegrationsOpen(true)}
          onLogout={() => {
            if (inDemo) clearDemoSession();
            else setStoredJwt(null);
            clearIntegrationStatusCache();
            setAuthenticated(false);
            setDemoStatus(null);
          }}
          onToggleLang={() => setLang(lang === "pl" ? "en" : "pl")}
          onReset={reset}
          t={t}
          demoLogoutLabel={inDemo ? t("demo.new_session") : t("login.logout")}
        />

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

        <main className="aw-workspace">
          <FadeIn delay={0.06}>
          {showBriefSetup && (
          <section className="space-y-10">
            <BriefForm
              onSubmit={handleStart}
              disabled={isActive || demoExhausted}
              selectedMode={mode}
              aggressiveSchema={aggressiveSchema}
              onAggressiveSchemaChange={setAggressiveSchema}
              onModeChange={setMode}
              maxDescriptionLen={maxBriefChars}
              allowedModes={allowedDemoModes}
              councilMode={councilMode}
            />
          </section>
          )}
          </FadeIn>

          {state.status === "safety_halt" && (
            <FadeIn>
            <div
              role="alert"
              className="aw-alert border-2 border-amber-500/60 bg-amber-950/50 space-y-3"
            >
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h2 className="text-[15px] font-semibold text-amber-100">
                  {t("safety.halt.title")}
                </h2>
                <span className="text-[22px] font-bold tracking-wide text-amber-300 tabular-nums">
                  116 123
                </span>
              </div>
              <p className="text-[13px] text-amber-100/90 leading-relaxed">
                {t("safety.halt.helpline")}{" "}
                <strong className="text-amber-200">116 123</strong>.
              </p>
              {state.safetyMessage ? (
                <p className="text-[13px] text-amber-50/80 border-t border-amber-500/30 pt-3">
                  {state.safetyMessage}
                </p>
              ) : null}
              <p className="text-[12px] text-amber-200/70">{t("safety.halt.footer")}</p>
            </div>
            </FadeIn>
          )}

          {state.status === "error" && (
            <FadeIn>
            <div className="space-y-3 no-print">
              <div className="aw-alert border-red-500/30 bg-red-900/10 text-red-400">
                {state.error ?? t("app.error.unknown")}
              </div>
              {(state.error === t("llm_key.missing_gate") ||
                state.error === t("llm_key.missing_stream") ||
                state.error === t("llm_key.invalid")) && (
                <button
                  type="button"
                  onClick={() => setSetupOpen(true)}
                  className="text-[13px] px-4 py-2.5 rounded-lg border border-teal/40 text-teal hover:bg-teal/15 transition-colors"
                >
                  {t("llm_key.open_settings")}
                </button>
              )}
              <button
                type="button"
                onClick={reset}
                className="text-[13px] px-4 py-2.5 rounded-lg bg-teal/20 border border-teal/45 text-teal font-medium hover:bg-teal/30 transition-colors"
              >
                {t("syez.new_debate.btn")}
              </button>
            </div>
            </FadeIn>
          )}

          {/* Wątek: zarchiwizowane wcześniejsze tury (Ruch 1: dane w state.turns; Ruch 2: render). */}
          {(state.turns?.length ?? 0) > 0 && (
            <div className="space-y-10">
              {state.turns!.map((turn, i) => (
                <PriorTurnView
                  key={`${turn.debateId ?? "t"}-${i}`}
                  turn={turn}
                  index={i}
                />
              ))}
            </div>
          )}

          {/* Bąbel promptu bieżącej tury — echo briefu/follow-upu usera tuż przed Radą.
              Pokazujemy też dla PIERWSZEJ tury (BriefForm znika po starcie, więc inaczej
              brief #1 nie byłby widoczny przy wyniku ani w zapisanej debacie). */}
          {state.currentPromptText && (agentList.length > 0 || state.synthesis) && (
            <FadeIn delay={0.04}>
            <div className="space-y-4">
              <SectionDivider
                label={(state.turns?.length ?? 0) > 0 ? t("thread.your_followup") : t("thread.your_brief")}
              />
              <div className="aw-prose-bubble-accent">
                {state.currentPromptText}
              </div>
            </div>
            </FadeIn>
          )}

          {agentList.length > 0 && (
            <FadeIn delay={0.05}>
            <section>
              <SectionDivider
                label={
                  (state.turns?.length ?? 0) > 0
                    ? `${t("thread.prior_turn")} #${state.turns!.length + 1} · ${t("app.section.council")}`
                    : t("app.section.council")
                }
                className="mb-6"
              />
              <CouncilCircle
                agents={agentList}
                tensions={state.liveTensions ?? []}
              />
            </section>
            </FadeIn>
          )}

          {(agentList.length > 0 ||
            state.status === "synthesizing" ||
            state.status === "done") && (
            <FadeIn delay={0.08}>
            <section>
              <SectionDivider label={t("app.section.synthesis")} className="mb-6" />
              <SyezPanel
                synthesis={state.synthesis}
                synthesisStructured={state.synthesisStructured}
                tensionAxis={state.tensionAxis}
                status={state.status}
                debateId={state.debateId}
                debateCost={state.debateCost}
                debateMode={state.debateMode}
                lastCommitmentEcho={state.lastCommitmentEcho}
                onContinueThread={
                  state.debateId
                    ? (followUp) =>
                        continueDebateThread(
                          {
                            previous_debate_id: state.debateId!,
                            follow_up: followUp,
                          },
                          { onNeedLlmKey: () => setSetupOpen(true) },
                        )
                    : undefined
                }
                onCommitStep={handleCommit}
                onNewDebate={reset}
              />
              {state.status === "done" && state.project?.id != null && (
                <CommitmentsTimeline projectId={state.project.id} />
              )}
              {state.status === "done" &&
                state.project?.id == null &&
                state.debateId != null && (
                  <DebateCommitments debateId={state.debateId} />
                )}
            </section>
            </FadeIn>
          )}
        </main>
      </div>
    </div>
  );
}
