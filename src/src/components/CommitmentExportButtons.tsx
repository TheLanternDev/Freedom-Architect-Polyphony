/**
 * CommitmentExportButtons — per-commitment eksport do Notion / Todoist / GCal.
 *
 * Wpina istniejące (dotąd nieosiągalne z UI) endpointy:
 *   POST /integrations/{notion|todoist|gcal}/export  { commitment_ids: [id] }
 *
 * Status konfiguracji integracji pobierany z /integrations/status (global ENV
 * backendu — nie per-tenant). Cache keyowany po tożsamości klienta (JWT/tenant),
 * żeby zmiana sesji nie serwowała starego wyniku.
 */
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders, getStoredTenantId } from "@/lib/apiAuth";
import { getStoredJwt } from "@/lib/tokenStorage";
import { useLang } from "@/lib/i18n";

type Target = "notion" | "todoist" | "gcal";

interface ConfiguredTargets {
  notion: boolean;
  todoist: boolean;
  gcal: boolean;
}

const EMPTY_TARGETS: ConfiguredTargets = {
  notion: false,
  todoist: false,
  gcal: false,
};

let statusCacheKey: string | null = null;
let statusPromise: Promise<ConfiguredTargets> | null = null;

function integrationStatusCacheKey(): string {
  const jwt = getStoredJwt();
  if (jwt) return `jwt:${jwt.slice(-16)}`;
  return `legacy:${getStoredTenantId()}`;
}

/** Czyść przy logout / zmianie tenanta — fail-closed na świeżym fetchu. */
export function clearIntegrationStatusCache(): void {
  statusPromise = null;
  statusCacheKey = null;
}

function parseStatusPayload(d: unknown): ConfiguredTargets {
  const o = d as Record<string, Record<string, unknown>> | null;
  return {
    notion: o?.notion?.configured === true,
    todoist: o?.todoist?.configured === true,
    gcal: o?.google_calendar?.configured === true,
  };
}

function fetchConfigured(): Promise<ConfiguredTargets> {
  const key = integrationStatusCacheKey();
  if (statusPromise && statusCacheKey === key) {
    return statusPromise;
  }
  statusCacheKey = key;
  statusPromise = fetch(`${getApiBase()}/integrations/status`, {
    headers: getApiAuthHeaders(),
  })
    .then(async (r) => {
      if (!r.ok) {
        clearIntegrationStatusCache();
        return EMPTY_TARGETS;
      }
      return parseStatusPayload(await r.json());
    })
    .catch(() => {
      clearIntegrationStatusCache();
      return EMPTY_TARGETS;
    });
  return statusPromise;
}

const LABEL: Record<Target, string> = {
  notion: "Notion",
  todoist: "Todoist",
  gcal: "GCal",
};

export function CommitmentExportButtons({ commitmentId }: { commitmentId: number }) {
  const { t } = useLang();
  const [configured, setConfigured] = useState<ConfiguredTargets | null>(null);
  const [state, setState] = useState<Partial<Record<Target, "busy" | "ok" | "err">>>({});

  useEffect(() => {
    let cancelled = false;
    void fetchConfigured().then((c) => {
      if (!cancelled) setConfigured(c);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!configured) return null;
  const targets = (Object.keys(LABEL) as Target[]).filter((k) => configured[k]);
  if (targets.length === 0) return null;

  async function exportTo(target: Target) {
    setState((s) => ({ ...s, [target]: "busy" }));
    try {
      const r = await fetch(`${getApiBase()}/integrations/${target}/export`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getApiAuthHeaders() },
        body: JSON.stringify({ commitment_ids: [commitmentId] }),
      });
      const d = r.ok ? await r.json() : null;
      const ok = r.ok && d?.exported?.[0]?.ok === true;
      setState((s) => ({ ...s, [target]: ok ? "ok" : "err" }));
    } catch {
      setState((s) => ({ ...s, [target]: "err" }));
    }
  }

  return (
    <span className="no-print inline-flex items-center gap-1.5">
      <span className="text-[9px] uppercase tracking-wide text-white/25">
        {t("integrations.export.label")}
      </span>
      {targets.map((tgt) => {
        const st = state[tgt];
        return (
          <button
            key={tgt}
            type="button"
            disabled={st === "busy" || st === "ok"}
            onClick={() => void exportTo(tgt)}
            title={st === "err" ? t("integrations.export.err") : LABEL[tgt]}
            className={`text-[10px] px-1.5 py-0.5 rounded border transition-colors disabled:cursor-not-allowed ${
              st === "ok"
                ? "border-teal/40 text-teal/90"
                : st === "err"
                  ? "border-amber-500/40 text-amber-200/90 hover:bg-amber-500/10"
                  : "border-white/15 text-white/45 hover:border-white/35 hover:text-white/75 disabled:opacity-40"
            }`}
          >
            {st === "busy" ? "…" : st === "ok" ? `${LABEL[tgt]} ✓` : LABEL[tgt]}
          </button>
        );
      })}
    </span>
  );
}
