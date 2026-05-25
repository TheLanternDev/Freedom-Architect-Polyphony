/**
 * Modal ustawień integracji: Notion / Todoist / Google Calendar.
 * Status pobierany z /integrations/status; eksport per-commitment.
 */
import { useEffect, useState } from "react";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { useLang } from "@/lib/i18n";

interface IntegrationStatus {
  notion: { configured: boolean };
  todoist: { configured: boolean };
  google_calendar: { configured: boolean; calendar_id: string };
}

interface Props {
  open: boolean;
  onClose: () => void;
}

export function IntegrationsModal({ open, onClose }: Props) {
  const { t } = useLang();
  const [status, setStatus] = useState<IntegrationStatus | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    fetch(`${getApiBase()}/integrations/status`, {
      headers: getApiAuthHeaders(),
    })
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => setStatus(null))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg mx-4 rounded-2xl border border-white/10 bg-navy/95 p-6 shadow-2xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[16px] font-medium text-white">
            {t("integrations.title")}
          </h2>
          <button
            onClick={onClose}
            className="text-white/30 hover:text-white/70 text-sm"
          >
            {t("setup.close")}
          </button>
        </div>

        {loading && (
          <p className="text-[12px] text-white/30">Loading...</p>
        )}

        {status && (
          <div className="space-y-4">
            <IntegrationRow
              name="Notion"
              configured={status.notion.configured}
              envHint="NOTION_API_KEY + NOTION_DATABASE_ID"
            />
            <IntegrationRow
              name="Todoist"
              configured={status.todoist.configured}
              envHint="TODOIST_API_KEY"
            />
            <IntegrationRow
              name="Google Calendar"
              configured={status.google_calendar.configured}
              envHint="GCAL_CREDENTIALS_JSON"
              extra={
                status.google_calendar.configured
                  ? `Calendar: ${status.google_calendar.calendar_id}`
                  : undefined
              }
            />
          </div>
        )}

        <p className="mt-5 text-[10px] text-white/25 leading-relaxed">
          {t("integrations.env_hint")}
        </p>
      </div>
    </div>
  );
}

function IntegrationRow({
  name,
  configured,
  envHint,
  extra,
}: {
  name: string;
  configured: boolean;
  envHint: string;
  extra?: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/[0.07] bg-white/[0.02] px-4 py-3">
      <div>
        <span className="text-[13px] text-white/80 font-medium">{name}</span>
        {extra && (
          <span className="block text-[10px] text-white/35 mt-0.5">
            {extra}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        <span
          className={`w-2 h-2 rounded-full ${configured ? "bg-green-500" : "bg-white/20"}`}
        />
        <span className="text-[10px] text-white/40">
          {configured ? "Active" : envHint}
        </span>
      </div>
    </div>
  );
}
