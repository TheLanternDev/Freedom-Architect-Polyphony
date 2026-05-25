import { useCallback, useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";
import {
  getApiBase,
  getStoredApiBaseOverride,
  setStoredApiBaseOverride,
} from "@/lib/apiBase";
import {
  getStoredArchitektApiKey,
  setStoredArchitektApiKey,
} from "@/lib/apiAuth";
import { APP_TELEMETRY_ENABLED } from "@/config/product";

type Props = {
  open: boolean;
  onClose: () => void;
  showStartupDismiss: boolean;
  onDismissStartup: () => void;
};

export function LocalSetupModal({
  open,
  onClose,
  showStartupDismiss,
  onDismissStartup,
}: Props) {
  const { t } = useLang();
  const [urlInput, setUrlInput] = useState("");
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [testStatus, setTestStatus] = useState<"idle" | "ok" | "fail">("idle");
  const [testDetail, setTestDetail] = useState("");

  const syncInputFromRuntime = useCallback(() => {
    setUrlInput(getApiBase() || "http://127.0.0.1:8000");
    setApiKeyInput(getStoredArchitektApiKey() ?? "");
  }, []);

  useEffect(() => {
    if (!open) return;
    syncInputFromRuntime();
    setTestStatus("idle");
    setTestDetail("");
  }, [open, syncInputFromRuntime]);

  useEffect(() => {
    const onChange = () => syncInputFromRuntime();
    window.addEventListener("aw-api-base-changed", onChange);
    return () => window.removeEventListener("aw-api-base-changed", onChange);
  }, [syncInputFromRuntime]);

  const applyUrl = () => {
    const raw = urlInput.trim();
    if (!raw) {
      setStoredApiBaseOverride(null);
    } else {
      setStoredApiBaseOverride(raw);
    }
    setStoredArchitektApiKey(apiKeyInput.trim() || null);
    syncInputFromRuntime();
  };

  const clearOverride = () => {
    setStoredApiBaseOverride(null);
    syncInputFromRuntime();
  };

  const runHealthTest = async () => {
    const base = urlInput.trim().replace(/\/+$/, "") || "http://127.0.0.1:8000";
    setTestStatus("idle");
    setTestDetail("");
    try {
      const res = await fetch(`${base}/health`, { method: "GET" });
      if (!res.ok) {
        setTestStatus("fail");
        setTestDetail(`HTTP ${res.status}`);
        return;
      }
      const j = (await res.json()) as { status?: string; version?: string };
      setTestStatus("ok");
      setTestDetail(
        j.version != null ? `status=${j.status ?? "?"} · v${j.version}` : "",
      );
    } catch (e) {
      setTestStatus("fail");
      setTestDetail(e instanceof Error ? e.message : String(e));
    }
  };

  if (!open) return null;

  return (
    <div
      className="no-print fixed inset-0 z-[80] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="aw-setup-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg rounded-xl border border-white/10 bg-navy shadow-2xl shadow-black/50 p-5 space-y-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <h2
          id="aw-setup-title"
          className="text-[15px] font-medium text-white tracking-tight"
        >
          {t("setup.title")}
        </h2>

        <p className="text-[12px] text-white/55 leading-relaxed">
          {t("setup.intro")}
        </p>

        <div className="space-y-1.5">
          <label className="text-[11px] uppercase tracking-wider text-white/35">
            {t("setup.url_label")}
          </label>
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="http://127.0.0.1:8000"
            className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-[13px] text-white placeholder:text-white/25 focus:outline-none focus:border-teal/50"
            autoComplete="off"
            spellCheck={false}
          />
        </div>

        <div className="space-y-1.5">
          <label className="text-[11px] uppercase tracking-wider text-white/35">
            {t("setup.architekt_api_label")}
          </label>
          <input
            type="password"
            value={apiKeyInput}
            onChange={(e) => setApiKeyInput(e.target.value)}
            placeholder={t("setup.architekt_api_placeholder")}
            className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-[13px] text-white placeholder:text-white/25 focus:outline-none focus:border-teal/50"
            autoComplete="off"
            spellCheck={false}
          />
          <p className="text-[10px] text-white/35 leading-snug">{t("setup.architekt_api_note")}</p>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={applyUrl}
            className="text-[12px] px-3 py-1.5 rounded-lg border border-teal/40 bg-teal/15 text-teal hover:bg-teal/25 transition-colors"
          >
            {t("setup.apply")}
          </button>
          <button
            type="button"
            onClick={runHealthTest}
            className="text-[12px] px-3 py-1.5 rounded-lg border border-white/15 bg-white/[0.06] hover:border-white/25 transition-colors"
          >
            {t("setup.test")}
          </button>
          {getStoredApiBaseOverride() != null && (
            <button
              type="button"
              onClick={clearOverride}
              className="text-[12px] px-3 py-1.5 rounded-lg border border-white/10 text-white/45 hover:text-white/70 transition-colors"
            >
              {t("setup.clear_override")}
            </button>
          )}
        </div>

        {testStatus === "ok" && (
          <p className="text-[12px] text-green-400/95">
            {t("setup.test_ok")}
            {testDetail ? ` — ${testDetail}` : ""}
          </p>
        )}
        {testStatus === "fail" && (
          <p className="text-[12px] text-red-400/95">
            {t("setup.test_fail")}
            {testDetail ? `: ${testDetail}` : ""}
          </p>
        )}

        <div className="rounded-lg border border-white/[0.07] bg-white/[0.03] px-3 py-2.5 space-y-2 text-[11px] text-white/50 leading-relaxed">
          <p>{t("setup.key_hint")}</p>
          <p className="text-amber-200/80">{t("setup.security_warn")}</p>
          <p>
            {APP_TELEMETRY_ENABLED
              ? t("setup.telemetry_on")
              : t("setup.telemetry_off")}
          </p>
        </div>

        <div className="flex flex-wrap gap-2 justify-end pt-1">
          <button
            type="button"
            onClick={onClose}
            className="text-[12px] px-3 py-1.5 rounded-lg border border-white/12 text-white/60 hover:text-white/90 transition-colors"
          >
            {t("setup.close")}
          </button>
          {showStartupDismiss && (
            <button
              type="button"
              onClick={onDismissStartup}
              className="text-[12px] px-3 py-1.5 rounded-lg border border-white/15 bg-white/[0.06] hover:bg-white/10 transition-colors"
            >
              {t("setup.dismiss_startup")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
