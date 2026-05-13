/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  /** Opcjonalny Bearer dla backendu z `ARCHITEKT_API_KEY` (publiczny hosting). */
  readonly VITE_ARCHITEKT_API_KEY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
