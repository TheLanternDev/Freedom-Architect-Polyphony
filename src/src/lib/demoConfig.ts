/**
 * Tryb demo interaktywnego — konfiguracja z /edition i status z /demo/status.
 */
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { setStoredJwt } from "@/components/LoginScreen";

export type DemoPublicConfig = {
  enabled: boolean;
  max_debates: number;
  max_brief_chars: number;
  allowed_modes: string[];
  allowed_categories: string[];
};

export type DemoStatus = {
  demo: boolean;
  debates_used?: number;
  debates_max?: number;
  debates_remaining?: number;
  config?: DemoPublicConfig;
};

const LS_DEMO = "aw_demo_session";

export function isDemoSession(): boolean {
  try {
    return localStorage.getItem(LS_DEMO) === "1";
  } catch {
    return false;
  }
}

export function setDemoSession(active: boolean): void {
  try {
    if (active) {
      localStorage.setItem(LS_DEMO, "1");
      localStorage.setItem("aw_jwt_enabled", "1");
    } else {
      localStorage.removeItem(LS_DEMO);
    }
    window.dispatchEvent(new Event("aw-auth-change"));
  } catch {
    /* ignore */
  }
}

export async function fetchEditionDemoConfig(): Promise<DemoPublicConfig | null> {
  try {
    const r = await fetch(`${getApiBase()}/edition`);
    if (!r.ok) return null;
    const j = await r.json();
    const demo = j?.demo as DemoPublicConfig | undefined;
    return demo?.enabled ? demo : null;
  } catch {
    return null;
  }
}

export async function fetchDemoStatus(): Promise<DemoStatus | null> {
  try {
    const r = await fetch(`${getApiBase()}/demo/status`, {
      headers: { ...getApiAuthHeaders() },
    });
    if (!r.ok) return null;
    return (await r.json()) as DemoStatus;
  } catch {
    return null;
  }
}

export async function startDemoSession(): Promise<{ ok: true } | { ok: false; error: string }> {
  try {
    const r = await fetch(`${getApiBase()}/auth/demo`, { method: "POST" });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      const detail = data.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : typeof detail?.message_pl === "string"
            ? detail.message_pl
            : `HTTP ${r.status}`;
      return { ok: false, error: msg };
    }
    const data = await r.json();
    setStoredJwt(data.access_token, data.display_name ?? "Gość demo");
    setDemoSession(true);
    return { ok: true };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Błąd sieci",
    };
  }
}

export function clearDemoSession(): void {
  setStoredJwt(null);
  setDemoSession(false);
}
