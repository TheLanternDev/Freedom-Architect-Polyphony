import { useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";
import { humanizeFetchFailure } from "@/lib/fetchErrors";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";

interface Row {
  id: number;
  created_at: string;
  mode: string;
  category: string;
  preview?: string;
}

interface Props {
  onSelect: (debateId: number) => void;
  disabled: boolean;
}

export function DebateHistory({ onSelect, disabled }: Props) {
  const { t } = useLang();
  const [rows, setRows] = useState<Row[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const id = window.setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
    }, 320);
    return () => window.clearTimeout(id);
  }, [searchInput]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (disabled) return;
      try {
        const q = debouncedSearch ? `&q=${encodeURIComponent(debouncedSearch)}` : "";
        const res = await fetch(`${getApiBase()}/history?limit=30${q}`, {
          headers: { ...getApiAuthHeaders() },
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = (await res.json()) as { debates: Row[] };
        if (!cancelled) {
          setRows(data.debates ?? []);
          setErr(null);
        }
      } catch (e) {
        if (!cancelled)
          setErr(humanizeFetchFailure(e, t));
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [disabled, t, debouncedSearch]);

  return (
    <div className="mt-8 pt-6 border-t border-white/[0.06]">
      <p className="text-[10px] uppercase tracking-widest text-white/35 px-2 mb-2">
        {t("history.title")}
      </p>
      <div className="px-2 mb-2">
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          disabled={disabled}
          placeholder={t("history.search_placeholder")}
          className="w-full rounded-lg border border-white/10 bg-black/25 px-2 py-1.5 text-[11px] text-white/80 placeholder:text-white/25 focus:outline-none focus:border-teal/40 disabled:opacity-40"
          autoComplete="off"
          spellCheck={false}
        />
      </div>
      {err && (
        <p className="text-[11px] text-amber-400/80 px-2 mb-2">{err}</p>
      )}
      <ul className="space-y-1 max-h-[40vh] overflow-y-auto pr-1">
        {rows.map((r) => (
          <li key={r.id}>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onSelect(r.id)}
              className={`
                w-full text-left rounded-lg px-2 py-2 text-[11px] leading-snug
                border border-transparent hover:border-white/10 hover:bg-white/[0.03]
                text-white/55 hover:text-white/90 transition-colors
                ${disabled ? "opacity-40 cursor-not-allowed" : ""}
              `}
            >
              <span className="text-white/25 font-mono text-[10px] mr-2">
                #{r.id}
              </span>
              <span className="text-teal/70">{r.mode}</span>
              <span className="text-white/25 mx-1">·</span>
              <span className="text-white/35">{r.category}</span>
              <span className="block text-white/45 mt-1 truncate">
                {r.preview ?? "—"}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {rows.length === 0 && !err && !disabled && (
        <p className="text-[11px] text-white/25 px-2">{t("history.empty")}</p>
      )}
    </div>
  );
}
