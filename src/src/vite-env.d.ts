/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** Opcjonalny Bearer dla backendu z `ARCHITEKT_API_KEY` (publiczny hosting). */
  readonly VITE_ARCHITEKT_API_KEY?: string;
  /** Ustaw `fa2` gdy backend ma `AW_COUNCIL_MODE=fa2` — etykiety trybu FA2 w UI. */
  readonly VITE_AW_COUNCIL_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
