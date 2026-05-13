/**
 * Opcjonalny klucz HTTP do backendu (`ARCHITEKT_API_KEY` po stronie serwera).
 * Źródła: `VITE_ARCHITEKT_API_KEY` (build) lub localStorage (modal „Połączenie”).
 */
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

export function getApiAuthHeaders(): Record<string, string> {
  let key = (import.meta.env.VITE_ARCHITEKT_API_KEY as string | undefined)?.trim();
  if (!key) {
    key = getStoredArchitektApiKey() ?? "";
  }
  return key ? { Authorization: `Bearer ${key}` } : {};
}
