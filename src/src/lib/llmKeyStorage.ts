/**
 * BYOK: klucz Anthropic użytkownika.
 * Tauri → keychain systemowy (Rust keyring). Web dev → sessionStorage (nie localStorage).
 * Wartość trzymana w pamięci procesu dla synchronicznego getApiAuthHeaders().
 */
import { invoke } from "@tauri-apps/api/core";
import { isTauriWebview } from "@/lib/tokenStorage";

const SESSION_KEY = "aw_llm_key_session";

let memoryKey: string | null = null;
let loadPromise: Promise<string | null> | null = null;

function readSessionKey(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const v = sessionStorage.getItem(SESSION_KEY)?.trim();
    return v || null;
  } catch {
    return null;
  }
}

function writeSessionKey(key: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (key == null || !key.trim()) {
      sessionStorage.removeItem(SESSION_KEY);
    } else {
      sessionStorage.setItem(SESSION_KEY, key.trim());
    }
  } catch {
    /* quota / private mode */
  }
}

/** W buildzie produkcyjnym wymagamy klucza po stronie klienta (BYOK). */
export function isLlmKeyRequired(): boolean {
  return import.meta.env.PROD;
}

export function getLlmKeySync(): string | null {
  return memoryKey;
}

export function hasLlmKeyConfigured(): boolean {
  return Boolean(getLlmKeySync()?.trim());
}

/** Ładuje klucz z keychain (Tauri) lub sessionStorage (web). Idempotentne. */
export async function loadLlmKey(): Promise<string | null> {
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    if (isTauriWebview()) {
      try {
        const v = (await invoke<string | null>("get_llm_key")) ?? null;
        memoryKey = v?.trim() || null;
      } catch {
        memoryKey = null;
      }
    } else {
      memoryKey = readSessionKey();
    }
    return memoryKey;
  })();
  return loadPromise;
}

export async function setLlmKey(key: string | null): Promise<void> {
  const trimmed = key?.trim() || null;
  memoryKey = trimmed;
  loadPromise = Promise.resolve(trimmed);
  if (isTauriWebview()) {
    if (trimmed) {
      await invoke("store_llm_key", { key: trimmed });
    } else {
      await invoke("clear_llm_key");
    }
  } else {
    writeSessionKey(trimmed);
  }
}

export async function clearLlmKey(): Promise<void> {
  await setLlmKey(null);
}

/** Maskowany podgląd (np. sk••••••••••••abc). */
export function maskLlmKey(key: string | null | undefined): string {
  const k = (key ?? "").trim();
  if (!k) return "";
  if (k.length <= 8) return "••••••••";
  return `${k.slice(0, 3)}${"•".repeat(Math.min(12, k.length - 6))}${k.slice(-3)}`;
}
