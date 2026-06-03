/**
 * P1-A5: przechowywanie JWT/API key — Tauri → localStorage (WebView izolowany);
 * web SPA → sessionStorage (krótsze okno przy XSS; pełne httpOnly wymaga BFF).
 */
const LS_JWT = "aw_jwt_token";

export function isTauriWebview(): boolean {
  return typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;
}

function authStorage(): Storage {
  if (typeof window === "undefined") {
    throw new Error("authStorage: brak window");
  }
  return isTauriWebview() ? localStorage : sessionStorage;
}

export function getStoredJwt(): string | null {
  try {
    const v = authStorage().getItem(LS_JWT)?.trim();
    return v || null;
  } catch {
    return null;
  }
}

export function setStoredJwt(token: string | null): void {
  try {
    const store = authStorage();
    if (token == null || !String(token).trim()) {
      store.removeItem(LS_JWT);
      if (!isTauriWebview()) {
        try {
          localStorage.removeItem(LS_JWT);
        } catch {
          /* migracja ze starego localStorage */
        }
      }
    } else {
      store.setItem(LS_JWT, String(token).trim());
    }
  } catch {
    /* quota / private mode */
  }
}

export function clearStoredJwt(): void {
  setStoredJwt(null);
}
