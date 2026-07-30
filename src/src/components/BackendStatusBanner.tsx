/**
 * Baner ze stanem backendu — jedyne miejsce, w którym user dowiaduje się,
 * DLACZEGO Rada nie odpowiada (review 2026-07-30).
 *
 * Pokazuje się tylko wtedy, gdy jest co powiedzieć:
 *   • starting     — informacyjnie, backend wstaje (PyInstaller cold start 3–10 s)
 *   • port_blocked / spawn_failed / unreachable — blokada + konkretna instrukcja
 * Przy `ready` / `reused_existing` / `autospawn_disabled` nie renderuje nic.
 */
import { AlertTriangle, Loader2 } from "lucide-react";
import {
  backendStatusI18nKey,
  isBackendBlocking,
  useBackendStatus,
} from "@/lib/backendStatus";
import { useLang } from "@/lib/i18n";
import { Icon } from "@/components/ui/Icon";

export function BackendStatusBanner() {
  const status = useBackendStatus();
  const { t } = useLang();

  if (!status) return null;
  const blocking = isBackendBlocking(status);
  const starting = status.status === "starting" || status.status === "pending";
  if (!blocking && !starting) return null;

  const msg = t(backendStatusI18nKey(status.status));

  return (
    <div
      role={blocking ? "alert" : "status"}
      aria-live={blocking ? "assertive" : "polite"}
      className={
        "no-print flex items-start gap-3 border-b px-6 py-2.5 text-[13px] leading-snug " +
        (blocking
          ? "border-red-500/30 bg-red-500/10 text-red-200"
          : "border-border bg-surface/60 text-text-secondary")
      }
    >
      <Icon
        icon={blocking ? AlertTriangle : Loader2}
        size="sm"
        className={blocking ? "mt-0.5 shrink-0" : "mt-0.5 shrink-0 animate-spin"}
      />
      <div className="min-w-0">
        <p>{msg}</p>
        {blocking && (
          // Ścieżka do logów prosto z launchera — nie zgadujemy jej w i18n,
          // bo zależy od OS-u i od AW_APP_DATA_DIR.
          <p className="mt-1 break-all opacity-70">
            {t("backend.status.logs_at")} {status.log_dir}
          </p>
        )}
        {status.build_id && (
          <p className="mt-1 opacity-60">build: {status.build_id}</p>
        )}
      </div>
    </div>
  );
}
