/**
 * Offline-first: banner + kolejkowanie briefów gdy brak sieci.
 */
import { useCallback, useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";

const LS_QUEUE_KEY = "aw_offline_queue";

export interface QueuedBrief {
  id: string;
  brief: Record<string, unknown>;
  queuedAt: string;
}

export function getOfflineQueue(): QueuedBrief[] {
  try {
    return JSON.parse(localStorage.getItem(LS_QUEUE_KEY) || "[]");
  } catch {
    return [];
  }
}

export function addToOfflineQueue(brief: Record<string, unknown>): QueuedBrief {
  const item: QueuedBrief = {
    id: crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    brief,
    queuedAt: new Date().toISOString(),
  };
  const queue = getOfflineQueue();
  queue.push(item);
  try {
    localStorage.setItem(LS_QUEUE_KEY, JSON.stringify(queue.slice(-20)));
  } catch {
    /* ignore */
  }
  return item;
}

export function removeFromOfflineQueue(id: string) {
  const queue = getOfflineQueue().filter((q) => q.id !== id);
  try {
    localStorage.setItem(LS_QUEUE_KEY, JSON.stringify(queue));
  } catch {
    /* ignore */
  }
}

export function clearOfflineQueue() {
  try {
    localStorage.removeItem(LS_QUEUE_KEY);
  } catch {
    /* ignore */
  }
}

export function OfflineBanner({
  onReplayBrief,
}: {
  onReplayBrief?: (brief: Record<string, unknown>) => void;
}) {
  const { t } = useLang();
  const [online, setOnline] = useState(() =>
    typeof navigator !== "undefined" ? navigator.onLine : true,
  );
  const [queue, setQueue] = useState<QueuedBrief[]>([]);

  useEffect(() => {
    const on = () => {
      setOnline(true);
      setQueue(getOfflineQueue());
    };
    const off = () => setOnline(false);
    window.addEventListener("online", on);
    window.addEventListener("offline", off);
    setQueue(getOfflineQueue());
    return () => {
      window.removeEventListener("online", on);
      window.removeEventListener("offline", off);
    };
  }, []);

  const replay = useCallback(
    (item: QueuedBrief) => {
      removeFromOfflineQueue(item.id);
      setQueue(getOfflineQueue());
      onReplayBrief?.(item.brief);
    },
    [onReplayBrief],
  );

  if (online && queue.length === 0) return null;

  return (
    <div className="no-print mx-6 mt-4 space-y-2">
      {!online && (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-[13px] text-amber-100/95 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          {t("offline.banner")}
        </div>
      )}

      {online && queue.length > 0 && (
        <div className="rounded-lg border border-teal/30 bg-teal/5 px-4 py-3">
          <p className="text-[12px] text-teal/90 mb-2">
            {t("offline.queued_count").replace("{n}", String(queue.length))}
          </p>
          <div className="space-y-1">
            {queue.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between gap-2"
              >
                <span className="text-[11px] text-white/50 truncate flex-1">
                  {String(item.brief.description ?? "").slice(0, 60)}...
                </span>
                <button
                  type="button"
                  onClick={() => replay(item)}
                  className="text-[10px] px-2 py-0.5 rounded border border-teal/30 text-teal/80 hover:bg-teal/10 transition-colors shrink-0"
                >
                  {t("offline.replay")}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
