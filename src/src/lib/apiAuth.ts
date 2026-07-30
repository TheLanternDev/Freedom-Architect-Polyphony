/**
 * Opcjonalny klucz HTTP do backendu (`ARCHITEKT_API_KEY` po stronie serwera).
 * Źródła: `VITE_ARCHITEKT_API_KEY` (build) lub localStorage (modal „Połączenie”).
 *
 * ⚠️  SECURITY NOTE — desktop-only:
 * P1-A5: JWT w tokenStorage (Tauri→localStorage, web SPA→sessionStorage).
 * API key nadal w localStorage (modal Połączenie) — tylko desktop/dev.
 */
import { clearStoredJwt, getStoredJwt } from "@/lib/tokenStorage";
import { getLlmKeySync } from "@/lib/llmKeyStorage";

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

// P0-2 follow-up: legacy ARCHITEKT_API_KEY nie niesie tożsamości, więc backend
// (api/http_guard.py) wymaga JAWNEGO nagłówka X-Tenant-Id (fail-closed, 403 bez
// niego). Desktop single-user deklaruje tenant "default" — to świadoma deklaracja
// klienta (jeden użytkownik = jeden tenant), nie cichy default po stronie serwera.
// Wdrożenia multi-user NIE używają tej ścieżki (JWT przez /auth/login).
const LS_TENANT_ID = "aw_tenant_id";
const DEFAULT_LEGACY_TENANT = "default";

export function getStoredTenantId(): string {
  if (typeof window === "undefined") return DEFAULT_LEGACY_TENANT;
  try {
    const v = localStorage.getItem(LS_TENANT_ID)?.trim();
    return v || DEFAULT_LEGACY_TENANT;
  } catch {
    return DEFAULT_LEGACY_TENANT;
  }
}

export function setStoredTenantId(tenantId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (tenantId == null || !String(tenantId).trim()) {
      localStorage.removeItem(LS_TENANT_ID);
    } else {
      localStorage.setItem(LS_TENANT_ID, String(tenantId).trim());
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

/** Zwraca true gdy JWT ma poprawną strukturę i exp > now. */
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

/**
 * VITE_ARCHITEKT_API_KEY: tylko w trybie deweloperskim (import.meta.env.DEV).
 * W buildzie produkcyjnym Vite inlinuje klucz do bundle — stałby się publiczny.
 */
function devBuildTimeKey(): string | undefined {
  return import.meta.env.DEV
    ? (import.meta.env.VITE_ARCHITEKT_API_KEY as string | undefined)?.trim() || undefined
    : undefined;
}

/**
 * JEDNO miejsce, które ustala poświadczenie do backendu — i nagłówki, i verdykt
 * „czy warto w ogóle wysyłać żądanie".
 *
 * PO CO (review 2026-07-30): `hasValidApiAuth()` i `getApiAuthHeaders()` liczyły
 * to samo dwa razy i rozjeżdżały się w jednym istotnym punkcie — headers przy
 * wygasłym JWT robiły `clearStoredJwt()`, a `hasValidApiAuth` nie. Pre-flight
 * w `useDebate` woła tylko to drugie, więc user mający JEDNOCZEŚNIE stary JWT
 * i ważny legacy API key dostawał „sesja wygasła" i zrzut do logowania —
 * dopóki jakiś inny komponent nie wywołał headers i nie wyczyścił tokenu.
 * Lockout zależny od kolejności renderów. Teraz jedna funkcja, jeden efekt.
 *
 * Świadomie zachowane: gdy w storage leży JWT (choćby wygasły), NIE spadamy do
 * legacy API key — serwer z aktywnym ARCHITEKT_JWT_SECRET odrzuca shared key,
 * więc lepszym sygnałem jest wymuszenie ponownego logowania.
 */
export function resolveAuth(opts?: { skipCache?: boolean }): {
  headers: Record<string, string>;
  valid: boolean;
} {
  const base = _councilAndLlmHeaders(opts);
  const jwt = getStoredJwt();

  if (jwt) {
    if (jwtNotExpired(jwt)) {
      return { headers: { Authorization: `Bearer ${jwt}`, ...base }, valid: true };
    }
    // Wygasły — usuwamy TU, żeby kolejne wywołanie (i pre-flight) widziało
    // już stan bez martwego tokenu.
    clearStoredJwt();
    return { headers: base, valid: false };
  }

  const key = devBuildTimeKey() ?? getStoredArchitektApiKey() ?? "";
  if (!key) {
    return { headers: base, valid: false };
  }
  return {
    headers: {
      Authorization: `Bearer ${key}`,
      ...base,
      // Legacy API key: backend wymaga jawnego tenanta (fail-closed) — bez tego 403.
      // Wysyłamy WYŁĄCZNIE na ścieżce API key; przy JWT tenant pochodzi z claimu
      // (nagłówek mógłby kolidować z enforce_tenant_header_match).
      "X-Tenant-Id": getStoredTenantId(),
    },
    valid: true,
  };
}

/**
 * Czy mamy JAKIEKOLWIEK ważne poświadczenie do backendu w tej chwili.
 * Pre-flight guard (useDebate) używa tego, żeby NIE wysyłać żądania bez auth,
 * które backend odrzuci 401-ką — a w spakowanej apce webview pokaże to jako
 * mylące „backend nie odpowiada".
 */
export function hasValidApiAuth(): boolean {
  return resolveAuth().valid;
}

export function getApiAuthHeaders(opts?: { skipCache?: boolean }): Record<string, string> {
  return resolveAuth(opts).headers;
}

function _councilAndLlmHeaders(opts?: { skipCache?: boolean }): Record<string, string> {
  const h: Record<string, string> = {};
  if (typeof window !== "undefined") {
    try {
      const m = localStorage.getItem("aw_council_mode");
      h["X-Council-Mode"] = m === "fa2" ? "fa2" : "personal";
    } catch {
      /* ignore */
    }
  }
  if (opts?.skipCache || getCacheSkip()) {
    h["X-AW-Cache"] = "skip";
  }
  const llmKey = getLlmKeySync();
  if (llmKey) {
    h["X-LLM-Key"] = llmKey;
  }
  return h;
}
