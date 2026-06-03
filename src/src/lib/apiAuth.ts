/**
 * Opcjonalny klucz HTTP do backendu (`ARCHITEKT_API_KEY` po stronie serwera).
 * Źródła: `VITE_ARCHITEKT_API_KEY` (build) lub localStorage (modal „Połączenie”).
 *
 * ⚠️  SECURITY NOTE — desktop-only:
 * P1-A5: JWT w tokenStorage (Tauri→localStorage, web SPA→sessionStorage).
 * API key nadal w localStorage (modal Połączenie) — tylko desktop/dev.
 */
import { clearStoredJwt, getStoredJwt } from "@/lib/tokenStorage";

const LS_ARCHITEKT_API_KEY = "aw_architekt_api_key";

export function getStoredArchitektApiKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const v = localStorage.getItem(LS_ARCHITEKT_API_KEY)?.trim();
    return v || null;
  } catch {
    return null;
  }
}

export function setStoredArchitektApiKey(key: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (key == null || !String(key).trim()) {
      localStorage.removeItem(LS_ARCHITEKT_API_KEY);
    } else {
      localStorage.setItem(LS_ARCHITEKT_API_KEY, String(key).trim());
    }
  } catch {
    /* quota / private mode */
  }
}

const LS_CACHE_SKIP = "aw_cache_skip";

export function setCacheSkip(skip: boolean): void {
  if (typeof window === "undefined") return;
  try {
    if (skip) localStorage.setItem(LS_CACHE_SKIP, "1");
    else localStorage.removeItem(LS_CACHE_SKIP);
  } catch {
    /* ignore */
  }
}

export function getCacheSkip(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return localStorage.getItem(LS_CACHE_SKIP) === "1";
  } catch {
    return false;
  }
}

/** Zwraca true gdy JWT ma poprawną strukturę i exp > now. Wygasłe odrzucamy
 *  od razu — żeby `getApiAuthHeaders` spadł do VITE_ARCHITEKT_API_KEY zamiast
 *  wysyłać Bearer, który backend i tak odrzuci 401-ką. */
function jwtNotExpired(token: string): boolean {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    const b64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
    const pad = b64.length % 4 === 0 ? b64 : b64 + "=".repeat(4 - (b64.length % 4));
    const payload = JSON.parse(atob(pad));
    const exp = Number(payload?.exp);
    return Number.isFinite(exp) && exp * 1000 > Date.now() + 5_000; // 5s margin
  } catch {
    return false;
  }
}

export function getApiAuthHeaders(opts?: { skipCache?: boolean }): Record<string, string> {
  let jwt: string | null = getStoredJwt();
  if (jwt && !jwtNotExpired(jwt)) {
    clearStoredJwt();
    jwt = null;
  }
  if (jwt) {
    const h: Record<string, string> = { Authorization: `Bearer ${jwt}` };
    if (typeof window !== "undefined") {
      try {
        const m = localStorage.getItem("aw_council_mode");
        h["X-Council-Mode"] = m === "fa2" ? "fa2" : "personal";
      } catch { /* ignore */ }
    }
    if (opts?.skipCache || getCacheSkip()) {
      h["X-AW-Cache"] = "skip";
    }
    return h;
  }

  // VITE_ARCHITEKT_API_KEY: tylko w trybie deweloperskim (import.meta.env.DEV).
  // W buildzie produkcyjnym Vite inlinuje klucz do bundle — staje się publiczny.
  // Fix: w produkcji ignorujemy zmienną build-time i używamy wyłącznie localStorage
  // (klucz ustawiony przez użytkownika w modalce Połączenie) lub JWT z /auth/login.
  let key = (import.meta.env.DEV
    ? (import.meta.env.VITE_ARCHITEKT_API_KEY as string | undefined)?.trim()
    : undefined);
  if (!key) {
    key = getStoredArchitektApiKey() ?? "";
  }
  const h: Record<string, string> = key ? { Authorization: `Bearer ${key}` } : {};
  if (typeof window !== "undefined") {
    try {
      const m = localStorage.getItem("aw_council_mode");
      h["X-Council-Mode"] = m === "fa2" ? "fa2" : "personal";
    } catch {
      /* ignore */
    }
  }
  // Cache bypass — przekazany jawnie lub z localStorage (toggle „świeża debata").
  if (opts?.skipCache || getCacheSkip()) {
    h["X-AW-Cache"] = "skip";
  }
  return h;
}
