/**
 * Panel notyfikacji / follow-up — pokazuje zobowiązania wymagające uwagi.
 * Polling co 60s + opcjonalne browser Notification API.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { useLang } from "@/lib/i18n";

interface DueRow {
  id: number;
  text: string;
  status: string;
  follow_up_at: string | null;
  needs_attention: number;
  trigger_type: string;
  project_id: number | null;
}

const POLL_MS = 60_000;
const LS_NOTIF_PERM = "aw_notif_permission";

export function NotificationsPanel() {
  const { t } = useLang();
  const [items, setItems] = useState<DueRow[]>([]);
  const [open, setOpen] = useState(false);
  const [notifEnabled, setNotifEnabled] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${getApiBase()}/commitments/due?within_hours=168`, {
        headers: getApiAuthHeaders(),
      });
      if (!r.ok) return;
      const data = await r.json();
      const rows: DueRow[] = data.commitments ?? [];
      setItems(rows);

      if (notifEnabled && rows.some((r) => r.needs_attention)) {
        _showBrowserNotification(rows.filter((r) => r.needs_attention).length);
      }
    } catch {
      /* offline */
    }
  }, [notifEnabled]);

  useEffect(() => {
    load();
    timerRef.current = setInterval(load, POLL_MS);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [load]);

  useEffect(() => {
    try {
      setNotifEnabled(localStorage.getItem(LS_NOTIF_PERM) === "1");
    } catch {
      /* ignore */
    }
  }, []);

  const requestNotifPermission = useCallback(async () => {
    if (!("Notification" in window)) return;
    const perm = await Notification.requestPermission();
    const granted = perm === "granted";
    setNotifEnabled(granted);
    try {
      localStorage.setItem(LS_NOTIF_PERM, granted ? "1" : "0");
    } catch {
      /* ignore */
    }
  }, []);

  const urgent = items.filter((i) => i.needs_attention);
  const upcoming = items.filter((i) => !i.needs_attention);

  return (
    <div className="no-print mt-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-[11px] uppercase tracking-widest text-white/30 hover:text-teal/70 transition-colors"
      >
        <span className="flex items-center gap-1.5">
          {t("notif.title")}
          {urgent.length > 0 && (
            <span className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-red-500/80 text-[9px] text-white font-bold">
              {urgent.length}
            </span>
          )}
        </span>
        <span>{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="mt-2 space-y-2 max-h-[300px] overflow-y-auto">
          {!notifEnabled && "Notification" in window && (
            <button
              type="button"
              onClick={requestNotifPermission}
              className="w-full text-[10px] px-2 py-1.5 rounded border border-teal/25 text-teal/70 hover:bg-teal/10 transition-colors"
            >
              {t("notif.enable_browser")}
            </button>
          )}

          {items.length === 0 && (
            <p className="text-[11px] text-white/25 px-1">
              {t("notif.empty")}
            </p>
          )}

          {urgent.map((row) => (
            <div
              key={row.id}
              className="rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-2"
            >
              <div className="flex items-center gap-1.5 mb-1">
                <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[9px] uppercase tracking-widest text-red-300/80">
                  {t("notif.needs_attention")}
                </span>
              </div>
              <p className="text-[11px] text-white/80 leading-snug line-clamp-3">
                {row.text}
              </p>
              {row.follow_up_at && (
                <span className="text-[9px] text-red-200/50 font-mono mt-1 block">
                  FU: {row.follow_up_at.slice(0, 16)}
                </span>
              )}
            </div>
          ))}

          {upcoming.map((row) => (
            <div
              key={row.id}
              className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2"
            >
              <p className="text-[11px] text-white/65 leading-snug line-clamp-2">
                {row.text}
              </p>
              {row.follow_up_at && (
                <span className="text-[9px] text-white/30 font-mono mt-1 block">
                  FU: {row.follow_up_at.slice(0, 16)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function _showBrowserNotification(count: number) {
  if (!("Notification" in window) || Notification.permission !== "granted") return;
  try {
    new Notification("Architekt Wolności", {
      body: `${count} zobowiązań wymaga uwagi — nie uciekaj od domknięcia.`,
      icon: "/src-tauri/icons/32x32.png",
      tag: "aw-followup",
    });
  } catch {
    /* ignore */
  }
}
