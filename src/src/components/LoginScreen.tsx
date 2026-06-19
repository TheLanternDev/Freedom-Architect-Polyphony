/**
 * Faza 4/7: ekran logowania / rejestracji multi-user.
 * JWT: tokenStorage (Tauri→localStorage, web→sessionStorage). P1-A5.
 */
import { useCallback, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { useLang } from "@/lib/i18n";
import {
  getStoredJwt as readJwt,
  setStoredJwt as writeJwt,
} from "@/lib/tokenStorage";
import {
  type DemoPublicConfig,
  startDemoSession,
} from "@/lib/demoConfig";

const LS_USER = "aw_user_display";

export function getStoredJwt(): string | null {
  return readJwt();
}

export function setStoredJwt(token: string | null, displayName?: string) {
  try {
    writeJwt(token);
    if (token && displayName) {
      localStorage.setItem(LS_USER, displayName);
    } else if (!token) {
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

      // Walidacja klienta zgodna z RegisterRequest/LoginRequest (api/routers/auth.py):
      // register: username ≥2, hasło ≥6; login: hasło ≥4. Czytelny komunikat zamiast 422.
      const minPw = mode === "register" ? 6 : 4;
      if (username.trim().length < 2 || password.length < minPw) {
        setError(`Nazwa min. 2 znaki, hasło min. ${minPw} znaków.`);
        setBusy(false);
        return;
      }

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
      <div className="aw-app-shell items-center justify-center">
        <div className="aw-card w-full max-w-md mx-4 shadow-elevated border-gold/20">
          <p className="aw-eyebrow mb-3">{t("demo.badge")}</p>
          <h1 className="font-display text-display-md text-text-primary mb-2">
            {t("app.brand")}
          </h1>
          <p className="aw-body mb-5">{t("demo.intro")}</p>
          <ul className="aw-caption space-y-1.5 mb-8 list-disc pl-4 marker:text-text-tertiary">
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
            className="aw-btn-primary w-full disabled:opacity-30"
          >
            {busy ? "..." : t("demo.btn_start")}
          </button>
          <p className="aw-caption mt-5 text-center">{t("demo.footer")}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="aw-app-shell items-center justify-center">
      <div className="aw-card w-full max-w-sm mx-4 shadow-elevated">
        <h1 className="font-display text-display-md text-text-primary mb-2">
          {t("app.brand")}
        </h1>
        <p className="aw-body mb-8">{t("login.subtitle")}</p>

        <div className="flex gap-2 mb-6">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`flex-1 text-[12px] py-2 rounded-control border transition-colors duration-premium ${mode === "login" ? "border-gold/40 bg-gold-dim text-gold" : "border-border text-text-tertiary hover:text-text-secondary"}`}
          >
            {t("login.tab_login")}
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            className={`flex-1 text-[12px] py-2 rounded-control border transition-colors duration-premium ${mode === "register" ? "border-gold/40 bg-gold-dim text-gold" : "border-border text-text-tertiary hover:text-text-secondary"}`}
          >
            {t("login.tab_register")}
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder={t("login.username")}
            autoComplete="username"
            className="aw-input-base"
          />
          {mode === "register" && (
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder={t("login.display_name")}
              className="aw-input-base"
            />
          )}
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t("login.password")}
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            className="aw-input-base"
          />

          {error && (
            <p className="text-[11px] text-red-400">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy || !username.trim() || password.length < 4}
            className="aw-btn-primary w-full disabled:opacity-30"
          >
            {busy
              ? "..."
              : mode === "login"
                ? t("login.btn_login")
                : t("login.btn_register")}
          </button>
        </form>

        {/* P2-E1: „Pomiń logowanie" tylko w dev — build produkcyjny dla
            klientów nie może oferować wejścia bez tożsamości. */}
        {import.meta.env.DEV && (
          <button
            type="button"
            onClick={skipLogin}
            className="aw-btn-ghost w-full mt-5"
          >
            {t("login.skip")}
          </button>
        )}
      </div>
    </div>
  );
}
