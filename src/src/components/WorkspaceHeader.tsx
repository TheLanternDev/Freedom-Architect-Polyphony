import {
  Globe,
  Link2,
  LogOut,
  RefreshCw,
  Settings,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";
import type { DebateState } from "@/types/debate";

interface Props {
  status: DebateState["status"];
  statusLabel: string;
  pendingMsg?: string;
  showPending: boolean;
  councilMode: "personal" | "fa2";
  inDemo: boolean;
  lang: "pl" | "en";
  isActive: boolean;
  authenticatedJwt: boolean;
  onCouncilModeSelect: (mode: "personal" | "fa2") => void;
  onOpenSetup: () => void;
  onOpenIntegrations: () => void;
  onLogout: () => void;
  onToggleLang: () => void;
  onReset: () => void;
  t: (key: string) => string;
  demoLogoutLabel: string;
}

const STATUS_STYLE: Record<string, string> = {
  idle: "aw-badge",
  agents_speaking: "aw-badge-active",
  synthesizing: "aw-badge-active",
  done: "border-green-500/30 bg-green-900/20 text-green-400",
  error: "border-red-500/30 bg-red-900/20 text-red-400",
  safety_halt: "border-amber-500/50 bg-amber-950/40 text-amber-200",
};

/** Compact workspace toolbar — status + essential controls only. */
export function WorkspaceHeader({
  status,
  statusLabel,
  pendingMsg,
  showPending,
  councilMode,
  inDemo,
  lang,
  isActive,
  authenticatedJwt,
  onCouncilModeSelect,
  onOpenSetup,
  onOpenIntegrations,
  onLogout,
  onToggleLang,
  onReset,
  t,
  demoLogoutLabel,
}: Props) {
  const displayStatus = showPending && pendingMsg ? pendingMsg : statusLabel;
  const statusClass = STATUS_STYLE[status] ?? STATUS_STYLE.idle;

  return (
    <header className="shrink-0 border-b border-border bg-surface/30 backdrop-blur-sm">
      <div className="px-6 lg:px-8 py-3.5 flex items-center gap-4">
        {/* Mobile title */}
        <div className="lg:hidden min-w-0 flex-1">
          <span className="font-display text-[17px] text-text-primary truncate">
            {t("app.title.supervisory")}{" "}
            <span className="aw-accent-highlight">{t("app.title.council")}</span>
          </span>
        </div>

        {/* Status — desktop: obok kontekstu workspace */}
        <div className="flex items-center gap-3 min-w-0 shrink-0">
          <span className="hidden lg:inline aw-eyebrow text-text-tertiary/80">
            {t("app.title.supervisory")} {t("app.title.council")}
          </span>
          <span
            className={cn(
              "inline-flex items-center gap-2 text-[11px] px-3 py-1 rounded-full border shrink-0",
              statusClass,
              isActive && status === "agents_speaking" && "animate-pulse",
            )}
          >
            {isActive && (
              <span className="w-1.5 h-1.5 rounded-full bg-teal-light shrink-0" />
            )}
            {displayStatus}
          </span>
        </div>

        <div className="flex-1 hidden lg:block" />

        {/* Council mode — segmented control */}
        {!inDemo && (
          <div
            className="no-print hidden sm:flex items-center rounded-control border border-border bg-surface-raised/50 p-0.5 shrink-0"
            role="group"
            aria-label="Tryb Rady"
          >
            {(["personal", "fa2"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => onCouncilModeSelect(mode)}
                disabled={isActive || councilMode === mode}
                className={cn(
                  "px-3 py-1 rounded-[6px] text-[11px] font-medium transition-all duration-premium",
                  "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1",
                  councilMode === mode
                    ? mode === "fa2"
                      ? "bg-amber-400/15 text-amber-200 focus-visible:outline-amber-400/40"
                      : "bg-teal-dim text-teal-light focus-visible:outline-teal/40"
                    : "text-text-tertiary hover:text-text-secondary focus-visible:outline-border",
                  isActive && "cursor-not-allowed opacity-50",
                )}
              >
                {mode === "personal" ? "Osobista" : "Biznesowa"}
              </button>
            ))}
          </div>
        )}

        {/* Utility actions */}
        <div className="no-print flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onOpenSetup}
            title={t("setup.btn_connection")}
            className="aw-btn-ghost px-2.5 py-1.5 hidden md:inline-flex"
          >
            <Icon icon={Settings} size="sm" className="text-text-tertiary" />
            <span className="hidden xl:inline">{t("setup.btn_connection")}</span>
          </button>

          {!inDemo && (
            <button
              type="button"
              onClick={onOpenIntegrations}
              title={t("integrations.title")}
              className="aw-btn-ghost px-2.5 py-1.5 hidden md:inline-flex"
            >
              <Icon icon={Link2} size="sm" className="text-text-tertiary" />
              <span className="hidden xl:inline">{t("integrations.title")}</span>
            </button>
          )}

          <button
            type="button"
            onClick={onToggleLang}
            title={t("app.lang.toggle_tooltip")}
            aria-label={t("app.lang.toggle_tooltip")}
            className="inline-flex items-center gap-0.5 text-[11px] px-2 py-1 rounded-control border border-border text-text-tertiary hover:border-teal/35 hover:text-teal-light transition-colors duration-premium focus-visible:outline focus-visible:outline-2 focus-visible:outline-teal/35 focus-visible:outline-offset-1"
          >
            <Icon icon={Globe} size="sm" />
            <span className={lang === "pl" ? "text-teal-light" : ""}>PL</span>
            <span className="text-text-tertiary/40">/</span>
            <span className={lang === "en" ? "text-teal-light" : ""}>EN</span>
          </button>

          {authenticatedJwt && (
            <button
              type="button"
              onClick={onLogout}
              title={demoLogoutLabel}
              className="aw-btn-ghost px-2 py-1.5"
            >
              <Icon icon={LogOut} size="sm" />
            </button>
          )}

          {status !== "idle" && (
            <button
              type="button"
              onClick={onReset}
              disabled={isActive}
              title={t("app.btn.reset")}
              className="aw-btn-ghost inline-flex items-center gap-1.5 px-2 py-1.5 disabled:opacity-35"
            >
              <Icon icon={RefreshCw} size="sm" />
              <span className="hidden sm:inline">{t("app.btn.reset")}</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
