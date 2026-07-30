/**
 * Stan backendu raportowany przez launcher Tauri (src-tauri/src/lib.rs).
 *
 * PO CO (review 2026-07-30): launcher miał już komendę `backend_startup_status`,
 * ale NIC w froncie jej nie wołało — a komentarz w Rust obiecywał, że UI pokaże
 * userowi konkretny powód. W efekcie „port zajęty", „brak binarki sidecara"
 * i „backend jeszcze wstaje" wyglądały identycznie: generyczne „backend nie
 * odpowiada", z jedynym śladem w pliku logu, o którym nikt nie wie.
 *
 * Kontrakt statusów trzymany zgodnie z `BackendStartupStatus` w lib.rs.
 * W przeglądarce (hosted web, `npm run dev`) nie ma launchera — hook zwraca
 * `null` i UI nie pokazuje nic.
 */
import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { isTauriWebview } from "@/lib/tokenStorage";

export type BackendStatusKind =
  | "pending"
  | "starting"
  | "ready"
  | "reused_existing"
  | "port_blocked"
  | "spawn_failed"
  | "unreachable"
  | "autospawn_disabled";

export interface BackendStatus {
  status: BackendStatusKind;
  build_id: string | null;
  port: number;
  log_dir: string;
}

const EVENT = "backend-status";

/** Statusy, przy których UI MUSI powiedzieć userowi, co jest nie tak. */
const BLOCKING: ReadonlySet<BackendStatusKind> = new Set([
  "port_blocked",
  "spawn_failed",
  "unreachable",
]);

export function isBackendBlocking(s: BackendStatus | null): boolean {
  return !!s && BLOCKING.has(s.status);
}

/** Klucz i18n z wyjaśnieniem — jeden na status, żeby komunikat był konkretny. */
export function backendStatusI18nKey(s: BackendStatusKind): string {
  return `backend.status.${s}`;
}

export function useBackendStatus(): BackendStatus | null {
  const [status, setStatus] = useState<BackendStatus | null>(null);

  useEffect(() => {
    if (!isTauriWebview()) return;
    let alive = true;
    let unlisten: (() => void) | undefined;

    // Odpytanie startowe: event mógł pójść PRZED zamontowaniem komponentu
    // (launcher startuje backend równolegle z ładowaniem webview), więc
    // sam listener by nie wystarczył.
    void invoke<BackendStatus>("backend_startup_status")
      .then((s) => {
        if (alive) setStatus(s);
      })
      .catch(() => {
        /* starsza wersja launchera bez tej komendy — brak baneru, nie crash */
      });

    void listen<BackendStatus>(EVENT, (e) => {
      if (alive) setStatus(e.payload);
    }).then((fn) => {
      if (alive) unlisten = fn;
      else fn();
    });

    return () => {
      alive = false;
      unlisten?.();
    };
  }, []);

  return status;
}
