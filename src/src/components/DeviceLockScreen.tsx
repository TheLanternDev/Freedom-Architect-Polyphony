/**
 * Ekran blokady urządzenia (device binding).
 *
 * Pokazywany, gdy backend zwraca status "locked" z /device/status — czyli
 * pieczęć instalacji pochodzi z INNEJ maszyny (np. ktoś skopiował folder
 * aplikacji na pendrive/chmurę i odpalił na innym komputerze).
 *
 * To NIE jest izolacja danych — to miękka bariera anty-kopiowanie. Komunikat
 * jest świadomie rzeczowy, bez fałszywego poczucia "twardego zabezpieczenia".
 */
import { useLang } from "@/lib/i18n";

interface Props {
  fingerprintCurrent?: string | null;
  fingerprintSealed?: string | null;
}

export function DeviceLockScreen({
  fingerprintCurrent,
  fingerprintSealed,
}: Props) {
  const { t } = useLang();

  return (
    <div className="aw-app-shell items-center justify-center">
      <div className="aw-card w-full max-w-md mx-4 shadow-elevated border-red-500/20">
        <p className="aw-eyebrow mb-3 text-red-400/80">
          {t("device_lock.badge")}
        </p>
        <h1 className="font-display text-display-md text-text-primary mb-3">
          {t("device_lock.title")}
        </h1>
        <p className="aw-body mb-5">{t("device_lock.body")}</p>

        <div className="aw-caption space-y-1.5 mb-6 rounded-control border border-border bg-surface-raised/40 p-3 font-mono text-[10px] text-text-tertiary">
          <div>
            {t("device_lock.fp_current")}: {fingerprintCurrent ?? "—"}
          </div>
          <div>
            {t("device_lock.fp_sealed")}: {fingerprintSealed ?? "—"}
          </div>
        </div>

        <p className="aw-caption mb-2 text-text-secondary">
          {t("device_lock.recovery_title")}
        </p>
        <pre className="aw-caption rounded-control border border-border bg-black/30 p-3 font-mono text-[11px] text-gold/90 whitespace-pre-wrap break-all">
          python -m tools.device_reset
        </pre>
        <p className="aw-caption mt-4 text-text-tertiary">
          {t("device_lock.footer")}
        </p>
      </div>
    </div>
  );
}
