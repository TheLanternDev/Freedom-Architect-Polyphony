/**
 * Model A (lokalny / BYOK): brak telemetrii do zewnętrznego operatora produktu.
 * Jeśli kiedyś dodasz zbieranie danych — tylko za wyraźną zgodą w UI (opt-in).
 */
export const APP_TELEMETRY_ENABLED = false as const;

/**
 * Tryb Rady — przełączany w oknie (jeden program, dwie wersje).
 * Klucz `aw_council_mode` w localStorage: "personal" (domyślnie) | "fa2".
 * Zmiana emituje event 'aw:council-mode' — komponenty subskrybują bez reloadu.
 */
export type CouncilMode = "personal" | "fa2";
export const COUNCIL_MODE_KEY = "aw_council_mode";
export const COUNCIL_MODE_EVENT = "aw:council-mode";

export function getCouncilMode(): CouncilMode {
  if (typeof window === "undefined") return "personal";
  try {
    return localStorage.getItem(COUNCIL_MODE_KEY) === "fa2" ? "fa2" : "personal";
  } catch {
    return "personal";
  }
}

export function setCouncilMode(mode: CouncilMode): void {
  try {
    localStorage.setItem(COUNCIL_MODE_KEY, mode);
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(COUNCIL_MODE_EVENT, { detail: mode }));
    }
  } catch {
    /* ignore */
  }
}

export function isCouncilFa2(): boolean {
  return getCouncilMode() === "fa2";
}
