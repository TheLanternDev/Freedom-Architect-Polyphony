import { useEffect, useState } from "react";
import { useLang } from "@/lib/i18n";
import { humanizeFetchFailure } from "@/lib/fetchErrors";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { SidebarSection } from "@/components/ui/SidebarSection";
import { cn } from "@/lib/cn";

interface Row {
  id: number;
  created_at: string;
  mode: string;
  category: string;
  preview?: string;
  parent_debate_id?: number | null;
  /** Liczone po stronie backendu w /history — root wątku, niezależnie od limitu listy. */
  root_debate_id?: number | null;
}

/** Wątek = jeden łańcuch debat połączonych przez parent_debate_id. */
interface Thread {
  rootId: number;
  latest: Row;
  /** Liczba tur w łańcuchu widoczna w obecnej liście /history. */
  turnCount: number;
}

/**
 * Grupuje płaską listę debat w wątki. Preferuje `root_debate_id` z backendu;
 * gdy go nie ma (np. stary backend), wraca do lokalnego cofania po
 * `parent_debate_id` z fallbackiem do samego siebie.
 */
function groupIntoThreads(rows: Row[]): Thread[] {
  const byId = new Map<number, Row>();
  for (const r of rows) byId.set(r.id, r);
  function rootOf(r: Row): number {
    if (r.root_debate_id != null) return r.root_debate_id;
    let cur: Row | undefined = r;
    const seen = new Set<number>();
    while (cur?.parent_debate_id != null) {
      if (seen.has(cur.id)) break;
      seen.add(cur.id);
      const parent = byId.get(cur.parent_debate_id);
      if (!parent) return cur.parent_debate_id;
      cur = parent;
    }
    return cur ? cur.id : r.id;
  }
  const groups = new Map<number, Row[]>();
  for (const r of rows) {
    const root = rootOf(r);
    const arr = groups.get(root) ?? [];
    arr.push(r);
    groups.set(root, arr);
  }
  const threads: Thread[] = [];
  for (const [rootId, arr] of groups) {
    arr.sort((a, b) => (a.created_at < b.created_at ? 1 : -1));
    threads.push({ rootId, latest: arr[0], turnCount: arr.length });
  }
  threads.sort((a, b) =>
    a.latest.created_at < b.latest.created_at ? 1 : -1,
  );
  return threads;
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
    <SidebarSection label={t("history.title")} className="flex flex-col min-h-0 h-full">
      <div className="flex flex-col min-h-0 flex-1 space-y-2">
        <input
          type="search"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          disabled={disabled}
          placeholder={t("history.search_placeholder")}
          className="shrink-0 w-full rounded-control border border-border bg-surface-raised/60 px-2.5 py-1.5 text-[11px] text-text-secondary placeholder:text-text-tertiary focus:outline-none focus:border-teal/40 disabled:opacity-40"
          autoComplete="off"
          spellCheck={false}
        />
        {err && (
          <p className="shrink-0 text-[11px] text-amber-400/80">{err}</p>
        )}
        <ul className="min-h-0 flex-1 space-y-0.5 overflow-y-auto aw-scroll -mx-0.5 px-0.5">
          {groupIntoThreads(rows).map((th) => (
            <li key={th.rootId}>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onSelect(th.latest.id)}
                className={cn(
                  "w-full text-left rounded-control px-2.5 py-2 text-[11px] leading-snug",
                  "border border-transparent hover:border-border hover:bg-white/[0.03]",
                  "text-text-tertiary hover:text-text-secondary transition-colors duration-premium",
                  disabled && "opacity-40 cursor-not-allowed",
                )}
              >
                <span className="text-text-tertiary/70 font-mono text-[10px] mr-1.5">
                  #{th.latest.id}
                </span>
                <span className="text-teal/80">{th.latest.mode}</span>
                <span className="text-text-tertiary/50 mx-1">·</span>
                <span className="text-text-tertiary">{th.latest.category}</span>
                {th.turnCount > 1 && (
                  <span className="ml-1.5 text-[9px] uppercase tracking-widest text-teal/70 bg-teal-dim border border-teal/20 rounded-full px-1.5 py-px align-middle">
                    {th.turnCount}× {t("thread.prior_turn").toLowerCase()}
                  </span>
                )}
                <span className="block text-text-secondary/80 mt-1 truncate">
                  {th.latest.preview ?? "—"}
                </span>
              </button>
            </li>
          ))}
        </ul>
        {rows.length === 0 && !err && !disabled && (
          <div className="shrink-0 rounded-control border border-border/60 bg-surface-raised/40 px-3 py-4 text-center">
            <p className="text-[12px] text-text-secondary leading-snug">
              {t("history.empty")}
            </p>
            <p className="mt-1.5 text-[10px] text-text-tertiary leading-snug">
              {t("history.empty_hint")}
            </p>
          </div>
        )}
      </div>
    </SidebarSection>
  );
}
