import { useCallback, useState } from "react";
import { useLang } from "@/lib/i18n";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { clearStoredJwt, getStoredJwt } from "@/lib/tokenStorage";
import { setStoredJwt } from "@/components/LoginScreen";

const DELETE_CONFIRM = "USUŃ MOJE KONTO";

type Props = {
  inDemo: boolean;
  onAccountDeleted?: () => void;
};

function privacyPolicyUrl(): string | null {
  const u = (import.meta.env.VITE_PRIVACY_URL as string | undefined)?.trim();
  return u || null;
}

export function AccountPrivacyPanel({ inDemo, onAccountDeleted }: Props) {
  const { t } = useLang();
  // Bump after a successful login/register so the panel re-reads JWT state
  // and swaps the auth form for the export/delete tools.
  const [authVersion, setAuthVersion] = useState(0);
  void authVersion;
  const hasJwt = getStoredJwt() != null;
  const [busy, setBusy] = useState<"idle" | "export" | "delete">("idle");
  const [confirmText, setConfirmText] = useState("");
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(
    null,
  );

  const runExport = useCallback(async () => {
    if (inDemo || !hasJwt) return;
    setBusy("export");
    setMessage(null);
    try {
      const base = getApiBase().replace(/\/+$/, "");
      const res = await fetch(`${base}/account/export`, {
        headers: { ...getApiAuthHeaders(), Accept: "application/json" },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        const detail = (err as { detail?: unknown }).detail;
        const text =
          typeof detail === "string"
            ? detail
            : typeof detail === "object" && detail && "message_pl" in detail
              ? String((detail as { message_pl: string }).message_pl)
              : `HTTP ${res.status}`;
        setMessage({ kind: "err", text });
        return;
      }
      const blob = await res.blob();
      const stamp = new Date().toISOString().slice(0, 10);
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `architekt-export-${stamp}.json`;
      a.click();
      URL.revokeObjectURL(a.href);
      setMessage({ kind: "ok", text: t("account.export_ok") });
    } catch (e) {
      setMessage({
        kind: "err",
        text: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy("idle");
    }
  }, [hasJwt, inDemo, t]);

  const runDelete = useCallback(async () => {
    if (inDemo || !hasJwt) return;
    if (confirmText !== DELETE_CONFIRM) {
      setMessage({ kind: "err", text: t("account.delete_confirm_mismatch") });
      return;
    }
    setBusy("delete");
    setMessage(null);
    try {
      const base = getApiBase().replace(/\/+$/, "");
      const res = await fetch(`${base}/account`, {
        method: "DELETE",
        headers: {
          ...getApiAuthHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ confirm: DELETE_CONFIRM }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setMessage({
          kind: "err",
          text:
            typeof (err as { detail?: string }).detail === "string"
              ? (err as { detail: string }).detail
              : `HTTP ${res.status}`,
        });
        return;
      }
      clearStoredJwt();
      setConfirmText("");
      setMessage({ kind: "ok", text: t("account.delete_ok") });
      onAccountDeleted?.();
    } catch (e) {
      setMessage({
        kind: "err",
        text: e instanceof Error ? e.message : String(e),
      });
    } finally {
      setBusy("idle");
    }
  }, [confirmText, hasJwt, inDemo, onAccountDeleted, t]);

  if (inDemo) {
    return (
      <p className="text-[12px] text-amber-200/85 leading-relaxed">
        {t("account.demo_blocked")}
      </p>
    );
  }

  if (!hasJwt) {
    return <AccountAuthForm onAuthenticated={() => setAuthVersion((v) => v + 1)} />;
  }

  const policyUrl = privacyPolicyUrl();

  return (
    <div className="space-y-4">
      <p className="text-[12px] text-white/55 leading-relaxed">{t("account.intro")}</p>

      {policyUrl && (
        <a
          href={policyUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-[12px] text-teal/90 hover:text-teal underline"
        >
          {t("account.privacy_link")}
        </a>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy !== "idle"}
          onClick={() => void runExport()}
          className="text-[12px] px-3 py-1.5 rounded-lg border border-teal/40 bg-teal/15 text-teal hover:bg-teal/25 disabled:opacity-50 transition-colors"
        >
          {busy === "export" ? t("account.exporting") : t("account.export_btn")}
        </button>
      </div>

      <div className="space-y-2 pt-2 border-t border-white/10">
        <p className="text-[11px] text-red-300/80">{t("account.delete_warn")}</p>
        <label className="text-[11px] uppercase tracking-wider text-white/35 block">
          {t("account.delete_label")}
        </label>
        <input
          type="text"
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder={DELETE_CONFIRM}
          className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-[13px] text-white placeholder:text-white/25 focus:outline-none focus:border-red-400/50"
          autoComplete="off"
        />
        <button
          type="button"
          disabled={busy !== "idle" || confirmText !== DELETE_CONFIRM}
          onClick={() => void runDelete()}
          className="text-[12px] px-3 py-1.5 rounded-lg border border-red-500/40 bg-red-500/10 text-red-300 hover:bg-red-500/20 disabled:opacity-40 transition-colors"
        >
          {busy === "delete" ? t("account.deleting") : t("account.delete_btn")}
        </button>
      </div>

      {message && (
        <p
          className={`text-[12px] ${message.kind === "ok" ? "text-green-400/95" : "text-red-400/95"}`}
        >
          {message.text}
        </p>
      )}
    </div>
  );
}

/**
 * Inline login/register form for the no-JWT state of the privacy panel.
 * Posts to the same /auth/login and /auth/register endpoints as LoginScreen
 * and stores the JWT via the shared tokenStorage path (fires aw-auth-change),
 * so the whole app picks up the new per-user, tenant-isolated session.
 * Backend rules: login password >= 4, register password >= 6, username >= 2.
 */
function AccountAuthForm({ onAuthenticated }: { onAuthenticated: () => void }) {
  const { t } = useLang();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const minPw = mode === "register" ? 6 : 4;
  const canSubmit = username.trim().length >= 2 && password.length >= minPw;

  const submit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!canSubmit || busy) return;
      setError(null);
      setBusy(true);
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const body: Record<string, string> = {
        username: username.trim(),
        password,
      };
      if (mode === "register" && displayName.trim()) {
        body.display_name = displayName.trim();
      }
      try {
        const base = getApiBase().replace(/\/+$/, "");
        const res = await fetch(`${base}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const data = (await res.json().catch(() => ({}))) as {
            detail?: unknown;
          };
          const detail = data.detail;
          setError(
            typeof detail === "string" ? detail : `HTTP ${res.status}`,
          );
          return;
        }
        const data = (await res.json()) as {
          access_token: string;
          display_name?: string;
        };
        setStoredJwt(data.access_token, data.display_name);
        onAuthenticated();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setBusy(false);
      }
    },
    [busy, canSubmit, displayName, mode, onAuthenticated, password, username],
  );

  return (
    <div className="space-y-4">
      <p className="text-[12px] text-white/55 leading-relaxed">
        {t("account.auth_intro")}
      </p>

      <div className="flex gap-1 p-0.5 rounded-lg bg-white/[0.04] border border-white/10">
        <button
          type="button"
          onClick={() => {
            setMode("login");
            setError(null);
          }}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${
            mode === "login"
              ? "bg-teal/20 text-teal"
              : "text-white/50 hover:text-white/70"
          }`}
        >
          {t("account.auth_tab_login")}
        </button>
        <button
          type="button"
          onClick={() => {
            setMode("register");
            setError(null);
          }}
          className={`flex-1 text-[11px] py-1.5 rounded-md transition-colors ${
            mode === "register"
              ? "bg-teal/20 text-teal"
              : "text-white/50 hover:text-white/70"
          }`}
        >
          {t("account.auth_tab_register")}
        </button>
      </div>

      <form onSubmit={submit} className="space-y-3">
        <input
          type="text"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          placeholder={t("account.auth_username")}
          autoComplete="username"
          spellCheck={false}
          className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-[13px] text-white placeholder:text-white/25 focus:outline-none focus:border-teal/50"
        />
        {mode === "register" && (
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder={t("account.auth_display_name")}
            className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-[13px] text-white placeholder:text-white/25 focus:outline-none focus:border-teal/50"
          />
        )}
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder={t("account.auth_password")}
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          className="w-full rounded-lg border border-white/15 bg-black/30 px-3 py-2 text-[13px] text-white placeholder:text-white/25 focus:outline-none focus:border-teal/50"
        />
        {mode === "register" && (
          <p className="text-[10px] text-white/35 leading-snug">
            {t("account.auth_pw_hint_register")}
          </p>
        )}

        {error && <p className="text-[12px] text-red-400/95">{error}</p>}

        <button
          type="submit"
          disabled={!canSubmit || busy}
          className="text-[12px] px-3 py-1.5 rounded-lg border border-teal/40 bg-teal/15 text-teal hover:bg-teal/25 disabled:opacity-40 transition-colors"
        >
          {busy
            ? t("account.auth_busy")
            : mode === "login"
              ? t("account.auth_btn_login")
              : t("account.auth_btn_register")}
        </button>
      </form>
    </div>
  );
}
