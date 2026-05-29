/**
 * Faza 4/7: ekran logowania / rejestracji multi-user.
 * Wysyła credentials do /auth/login lub /auth/register, zapisuje JWT w localStorage.
 */
import { useCallback, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { useLang } from "@/lib/i18n";
import {
  type DemoPublicConfig,
  startDemoSession,
} from "@/lib/demoConfig";

const LS_JWT = "aw_jwt_token";
const LS_USER = "aw_user_display";

export function getStoredJwt(): string | null {
  try {
    return localStorage.getItem(LS_JWT);
  } catch {
    return null;
  }
}

export function setStoredJwt(token: string | null, displayName?: string) {
  try {
    if (token) {
      localStorage.setItem(LS_JWT, token);
      if (displayName) localStorage.setItem(LS_USER, displayName);
    } else {
      localStorage.removeItem(LS_JWT);
      localStorage.removeItem(LS_USER);
    }
    window.dispatchEvent(new Event("aw-auth-change"));
  } catch {
    /* ignore */
  }
}

export function getStoredUserDisplay(): string | null {
  try {
    return localStorage.getItem(LS_USER);
  } catch {
    return null;
  }
}

interface Props {
  onAuthenticated: () => void;
  demoConfig?: DemoPublicConfig | null;
}

export function LoginScreen({ onAuthenticated, demoConfig }: Props) {
  const { t } = useLang();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setBusy(true);

      const endpoint =
        mode === "login" ? "/auth/login" : "/auth/register";
      const body: Record<string, string> = {
        username: username.trim(),
        password,
      };
      if (mode === "register" && displayName.trim()) {
        body.display_name = displayName.trim();
      }

      try {
        const res = await fetch(`${getApiBase()}${endpoint}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(data.detail || `HTTP ${res.status}`);
          return;
        }
        const data = await res.json();
        setStoredJwt(data.access_token, data.display_name);
        onAuthenticated();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Błąd sieci");
      } finally {
        setBusy(false);
      }
    },
    [mode, username, password, displayName, onAuthenticated],
  );

  const skipLogin = useCallback(() => {
    setStoredJwt(null);
    onAuthenticated();
  }, [onAuthenticated]);

  const startDemo = useCallback(async () => {
    setError(null);
    setBusy(true);
    try {
      const result = await startDemoSession();
      if (!result.ok) {
        setError(result.error);
        return;
      }
      onAuthenticated();
    } finally {
      setBusy(false);
    }
  }, [onAuthenticated]);

  if (demoConfig?.enabled) {
    return (
      <div className="min-h-screen bg-navy flex items-center justify-center">
        <div className="w-full max-w-md mx-4 rounded-2xl border border-amber-400/20 bg-white/[0.02] p-6 shadow-2xl">
          <p className="text-[10px] uppercase tracking-widest text-amber-300/80 mb-2">
            {t("demo.badge")}
          </p>
          <h1 className="text-[20px] font-medium text-white mb-1">
            {t("app.brand")}
          </h1>
          <p className="text-[12px] text-white/45 mb-4 leading-relaxed">
            {t("demo.intro")}
          </p>
          <ul className="text-[11px] text-white/35 space-y-1 mb-6 list-disc pl-4">
            <li>
              {t("demo.limit_debates").replace(
                "{n}",
                String(demoConfig.max_debates),
              )}
            </li>
            <li>
              {t("demo.limit_chars").replace(
                "{n}",
                String(demoConfig.max_brief_chars),
              )}
            </li>
            <li>{t("demo.limit_ephemeral")}</li>
          </ul>
          {error && <p className="text-[11px] text-red-400 mb-3">{error}</p>}
          <button
            type="button"
            disabled={busy}
            onClick={() => void startDemo()}
            className="w-full py-2.5 rounded-lg bg-teal text-navy font-medium text-[13px] hover:bg-teal-light transition-colors disabled:opacity-30"
          >
            {busy ? "..." : t("demo.btn_start")}
          </button>
          <p className="text-[10px] text-white/25 mt-4 text-center leading-relaxed">
            {t("demo.footer")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-navy flex items-center justify-center">
      <div className="w-full max-w-sm mx-4 rounded-2xl border border-white/10 bg-white/[0.02] p-6 shadow-2xl">
        <h1 className="text-[20px] font-medium text-white mb-1">
          {t("app.brand")}
        </h1>
        <p className="text-[12px] text-white/40 mb-6">
          {t("login.subtitle")}
        </p>

        <div className="flex gap-2 mb-5">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`flex-1 text-[12px] py-1.5 rounded-lg border transition-colors ${mode === "login" ? "border-teal/50 bg-teal/10 text-teal" : "border-white/10 text-white/40 hover:text-white/60"}`}
          >
            {t("login.tab_login")}
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            className={`flex-1 text-[12px] py-1.5 rounded-lg border transition-colors ${mode === "register" ? "border-teal/50 bg-teal/10 text-teal" : "border-white/10 text-white/40 hover:text-white/60"}`}
          >
            {t("login.tab_register")}
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t("login.username")}
            autoComplete="username"
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-[13px] text-white placeholder:text-white/20 focus:outline-none focus:border-teal/60"
          />
          {mode === "register" && (
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("login.display_name")}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-[13px] text-white placeholder:text-white/20 focus:outline-none focus:border-teal/60"
            />
          )}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("login.password")}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2.5 text-[13px] text-white placeholder:text-white/20 focus:outline-none focus:border-teal/60"
          />

          {error && (
            <p className="text-[11px] text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy || !username.trim() || password.length < 4}
            className="w-full py-2.5 rounded-lg bg-teal text-navy font-medium text-[13px] hover:bg-teal-light transition-colors disabled:opacity-30"
          >
            {busy
              ? "..."
              : mode === "login"
                ? t("login.btn_login")
                : t("login.btn_register")}
          </button>
        </form>

        <button
          type="button"
          onClick={skipLogin}
          className="w-full mt-4 text-[11px] text-white/25 hover:text-white/50 transition-colors"
        >
          {t("login.skip")}
        </button>
      </div>
    </div>
  );
}
