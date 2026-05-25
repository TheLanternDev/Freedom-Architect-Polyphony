/**
 * Bazowy URL backendu FastAPI.
 *
 * W `vite build` + Tauri `import.meta.env.PROD` jest true, a origin webview
 * nie serwuje `/debate/*` — relatywne URL-e kończyły się na „Load failed”.
 * Gdy wykryjemy Tauri (lub `file:`), domyślnie wołamy API na localhost.
 *
 * W `vite` dev (npm run dev): domyślnie pusty string → żądania względne
 * (`/health`, …) trafiają w proxy z `vite.config.ts` na :8000 (bez CORS).
 *
 * Nadpisanie z UI (Tydzień 2): `localStorage["aw_api_base_override"]` — pierwszeństwo
 * przed `VITE_API_URL`, żeby użytkownik mógł zmienić backend bez przebudowy.
 */
const DEFAULT_LOCAL_API = "http://127.0.0.1:8000";
const LS_API_BASE = "aw_api_base_override";

export function getStoredApiBaseOverride(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const v = localStorage.getItem(LS_API_BASE)?.trim();
    return v || null;
  } catch {
    return null;
  }
}

/** Zapisuje lub czyści nadpisanie URL API; emituje `aw-api-base-changed`. */
export function setStoredApiBaseOverride(url: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (url == null || !String(url).trim()) {
      localStorage.removeItem(LS_API_BASE);
    } else {
      const u = String(url).trim().replace(/\/+$/, "");
      localStorage.setItem(LS_API_BASE, u);
    }
    window.dispatchEvent(new Event("aw-api-base-changed"));
  } catch {
    /* quota / private mode */
  }
}

function isTauriWebview(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function needsLocalApiFallback(): boolean {
  if (typeof window === "undefined") return false;
  try {
    const p = window.location?.protocol ?? "";
    if (p === "file:" || p === "chrome-extension:") return true;
  } catch {
    /* ignore */
  }
  return false;
}

export function getApiBase(): string {
  const stored = getStoredApiBaseOverride();
  if (stored) return stored;

  const fromEnv = (import.meta.env.VITE_API_URL as string | undefined)?.trim();
  if (fromEnv) return fromEnv;

  if (import.meta.env.DEV) {
    // Pusty origin → żądania względne (`/health`, `/debate/…`) idą na serwer Vite,
    // który proxy w `vite.config.ts` przekazuje na :8000 — bez CORS i bez
    // „gołego” 127.0.0.1 z webview. Nadal musisz mieć uruchomiony backend na 8000.
    return "";
  }

  if (isTauriWebview() || needsLocalApiFallback()) {
    return DEFAULT_LOCAL_API;
  }

  return "";
}
