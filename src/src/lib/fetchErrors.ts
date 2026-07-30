/**
 * Mapuje surowe wyjątki `fetch()` (często bezużyteczne: „Load failed”, „Failed to fetch”)
 * na komunikaty opisowe — z tłumaczeniem przez przekazaną funkcję `translate`.
 */

import { isTauriWebview } from "@/lib/tokenStorage";

export type TranslateFn = (key: string) => string;

const LOAD_FAILED_HINT = /\bload\s*failed\b/i;
const FETCH_FAILED_LOWER = "failed to fetch";

function unreachableKey(): string {
  // W paczce desktop (Tauri) backend to lokalny sidecar, nie proces
  // odpalany ręcznie przez usera — komunikat "uruchom uvicorn ręcznie"
  // jest tam niewykonalny (brak repo/terminala) i myli testerów.
  return isTauriWebview()
    ? "debate.network.unreachable_desktop"
    : "debate.network.unreachable";
}

export function humanizeFetchFailure(
  err: unknown,
  translate: TranslateFn,
): string {
  if (err instanceof DOMException && err.name === "AbortError") {
    return translate("debate.network.abort");
  }
  if (!(err instanceof Error)) {
    return translate("debate.network.unknown");
  }

  const m = err.message.trim();
  const lower = m.toLowerCase();

  if (!m) {
    return translate("debate.network.unknown");
  }

  if (LOAD_FAILED_HINT.test(m)) {
    return translate(unreachableKey());
  }
  if (lower === FETCH_FAILED_LOWER || lower.includes("failed to fetch")) {
    return translate(unreachableKey());
  }
  // Firefox: „NetworkError when attempting to fetch resource.”
  if (lower.includes("networkerror") && lower.includes("fetch")) {
    return translate(unreachableKey());
  }

  return m;
}
