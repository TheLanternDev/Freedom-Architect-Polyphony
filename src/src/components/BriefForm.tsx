import { useEffect, useMemo, useState } from "react";
import { useLang } from "@/lib/i18n";
import type { Brief } from "@/types/debate";
import { VoiceBriefButton } from "@/components/VoiceBriefButton";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";

const ONBOARD_KEY = "aw-onboarding-dismissed";

/** Limit zgodny z modelem Brief.extra_context po stronie backendu (max_length=8000). */
const EXTRA_CONTEXT_MAX = 8000;
const TEXT_EXTS = ["txt", "md", "csv", "json", "log", "text"];
/** Formaty binarne — ekstrakcja przez backend /attachment/extract. */
const DOC_EXTS = ["pdf", "docx"];

interface Attachment {
  name: string;
  content: string;
}

interface Props {
  onSubmit: (brief: Brief) => void;
  disabled: boolean;
  selectedMode: Brief["mode"];
  aggressiveSchema: boolean;
  onAggressiveSchemaChange: (v: boolean) => void;
  onModeChange?: (m: Brief["mode"]) => void;
  maxDescriptionLen?: number;
  allowedModes?: string[];
}

export function BriefForm({
  onSubmit,
  disabled,
  selectedMode,
  aggressiveSchema,
  onAggressiveSchemaChange,
  onModeChange,
  maxDescriptionLen = 8000,
  allowedModes,
}: Props) {
  const { lang, t } = useLang();
  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<Brief["category"]>("decyzja");
  const [showOnboard, setShowOnboard] = useState(true);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [attachNote, setAttachNote] = useState("");

  useEffect(() => {
    try {
      setShowOnboard(!window.localStorage.getItem(ONBOARD_KEY));
    } catch {
      setShowOnboard(true);
    }
  }, []);

  const MAX_LEN = maxDescriptionLen;
  const charCount = description.length;
  const overLimit = charCount > MAX_LEN;

  const templates = useMemo(
    () =>
      [
        {
          labelKey: "brief.tpl.quit.label",
          descKey: "brief.tpl.quit",
          mode: "pelna" as const,
          category: "decyzja" as const,
        },
        {
          labelKey: "brief.tpl.dream.label",
          descKey: "brief.tpl.dream",
          mode: "marzen" as const,
          category: "marzenie" as const,
        },
        {
          labelKey: "brief.tpl.pattern.label",
          descKey: "brief.tpl.pattern",
          mode: "schematy" as const,
          category: "schemat" as const,
        },
      ],
    [],
  );

  function dismissOnboarding() {
    try {
      window.localStorage.setItem(ONBOARD_KEY, "1");
    } catch {
      /* ignore */
    }
    setShowOnboard(false);
  }

  function applyTemplate(
    descKey: string,
    mode: Brief["mode"],
    cat: Brief["category"],
  ) {
    setDescription(t(descKey));
    setCategory(cat);
    onAggressiveSchemaChange(false);
    onModeChange?.(mode);
  }

  async function extractViaBackend(f: File): Promise<string> {
    const form = new FormData();
    form.append("file", f, f.name);
    const res = await fetch(`${getApiBase()}/attachment/extract`, {
      method: "POST",
      headers: getApiAuthHeaders(),
      body: form,
    });
    if (!res.ok) throw new Error(String(res.status));
    const data = await res.json();
    return typeof data.text === "string" ? data.text : "";
  }

  async function handleFiles(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = ""; // pozwól wybrać ten sam plik ponownie
    const skipped: string[] = [];
    const accepted: Attachment[] = [];
    for (const f of files) {
      const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
      const isText = TEXT_EXTS.includes(ext) || f.type.startsWith("text/");
      const isDoc = DOC_EXTS.includes(ext);
      if (!isText && !isDoc) {
        skipped.push(f.name);
        continue;
      }
      try {
        const content = isDoc ? await extractViaBackend(f) : await f.text();
        if (content.trim()) accepted.push({ name: f.name, content });
        else skipped.push(f.name);
      } catch {
        skipped.push(f.name);
      }
    }
    if (accepted.length) {
      setAttachments((prev) => [...prev, ...accepted]);
    }
    setAttachNote(skipped.length ? t("brief.attach.unsupported") + skipped.join(", ") : "");
  }

  function removeAttachment(idx: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
    setAttachNote("");
  }

  /** Skleja załączniki w extra_context z twardym limitem backendu (2000 zn.). */
  function buildExtraContext(): { value?: string; truncated: boolean } {
    if (!attachments.length) return { value: undefined, truncated: false };
    const blocks = attachments.map((a) => `[${a.name}]\n${a.content.trim()}`);
    const joined = blocks.join("\n\n");
    if (joined.length <= EXTRA_CONTEXT_MAX) {
      return { value: joined, truncated: false };
    }
    return { value: joined.slice(0, EXTRA_CONTEXT_MAX), truncated: true };
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (description.trim().split(/\s+/).length < 5 || overLimit) return;
    const mode: Brief["mode"] = aggressiveSchema ? "schematy" : selectedMode;
    const { value: extraContext, truncated } = buildExtraContext();
    if (truncated) setAttachNote(t("brief.attach.truncated"));
    onSubmit({
      description: description.trim(),
      category,
      mode,
      ...(extraContext ? { extra_context: extraContext } : {}),
      scale: "startup",
      budget: "medium",
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {showOnboard && (
        <div className="rounded-xl border border-teal/25 bg-teal/[0.06] px-4 py-3 flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-widest text-teal/80 mb-1">
              {t("brief.onboarding.title")}
            </p>
            <p className="text-[13px] text-white/75 leading-snug">{t("brief.onboarding.body")}</p>
          </div>
          <button
            type="button"
            onClick={dismissOnboarding}
            className="no-print shrink-0 self-start text-[11px] px-3 py-1.5 rounded-lg border border-teal/35 text-teal hover:bg-teal/15 transition-colors"
          >
            {t("brief.onboarding.dismiss")}
          </button>
        </div>
      )}

      <div>
        <p className="text-[11px] uppercase tracking-widest text-white/35 mb-2">
          {t("brief.quick.title")}
        </p>
        <div className="flex flex-wrap gap-2">
          {templates
            .filter(
              (tpl) =>
                !allowedModes?.length || allowedModes.includes(tpl.mode),
            )
            .map((tpl) => (
            <button
              key={tpl.labelKey}
              type="button"
              disabled={disabled}
              onClick={() => applyTemplate(tpl.descKey, tpl.mode, tpl.category)}
              className="text-[11px] px-3 py-1.5 rounded-full border border-white/12 bg-white/[0.03] hover:border-teal/40 hover:bg-teal/10 disabled:opacity-35 transition-colors"
            >
              {t(tpl.labelKey)}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="flex items-center justify-between gap-2 mb-1">
          <label className="block text-[12px] text-white/50 uppercase tracking-wider">
            {t("brief.label")}
          </label>
          <VoiceBriefButton
            disabled={disabled}
            lang={lang}
            onTranscript={(said) =>
              setDescription((prev) => (prev ? `${prev} ${said}` : said))
            }
            labelIdle={t("brief.voice.idle")}
            labelListening={t("brief.voice.active")}
            unsupportedHint={t("brief.voice.unsupported")}
          />
        </div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={disabled}
          placeholder={t("brief.placeholder")}
          rows={4}
          className={`w-full bg-white/5 border rounded-lg px-4 py-3 text-[14px] text-white placeholder:text-white/20 resize-none focus:outline-none transition-colors disabled:opacity-40 ${overLimit ? "border-red-500/70 focus:border-red-500" : "border-white/10 focus:border-teal/60"}`}
        />
        {charCount > 0 && (
          <div className={`text-[11px] mt-1 text-right ${overLimit ? "text-red-400" : "text-white/30"}`}>
            {charCount.toLocaleString()} / {MAX_LEN.toLocaleString()}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center gap-3 flex-wrap">
          <label className="no-print inline-flex items-center gap-2 text-[12px] px-3 py-1.5 rounded-lg border border-white/12 bg-white/[0.03] hover:border-teal/40 hover:bg-teal/10 cursor-pointer transition-colors aria-disabled:opacity-35">
            <input
              type="file"
              multiple
              accept=".txt,.md,.csv,.json,.log,.text,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
              disabled={disabled}
              onChange={handleFiles}
              className="hidden"
            />
            📎 {t("brief.attach.btn")}
          </label>
          <span className="text-[11px] text-white/35">{t("brief.attach.hint")}</span>
        </div>
        {attachments.length > 0 && (
          <ul className="mt-2 space-y-1">
            {attachments.map((a, i) => (
              <li
                key={`${a.name}-${i}`}
                className="flex items-center justify-between gap-2 text-[12px] bg-white/[0.03] border border-white/10 rounded-md px-3 py-1.5"
              >
                <span className="truncate text-white/70">
                  {a.name}{" "}
                  <span className="text-white/30">
                    ({a.content.length.toLocaleString()})
                  </span>
                </span>
                <button
                  type="button"
                  onClick={() => removeAttachment(i)}
                  disabled={disabled}
                  className="no-print shrink-0 text-[11px] text-white/40 hover:text-red-400 transition-colors disabled:opacity-35"
                >
                  {t("brief.attach.remove")}
                </button>
              </li>
            ))}
          </ul>
        )}
        {attachNote && (
          <p className="text-[11px] text-amber-400/80 mt-1">{attachNote}</p>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-[12px] text-white/50 mb-1 uppercase tracking-wider">
            {t("brief.category")}
          </label>
          <select
            value={category}
            onChange={(e) =>
              setCategory(e.target.value as Brief["category"])
            }
            disabled={disabled}
            className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-white focus:outline-none focus:border-teal/60 disabled:opacity-40"
          >
            <option value="decyzja">{t("brief.category.decision")}</option>
            <option value="projekt">{t("brief.category.project")}</option>
            <option value="marzenie">{t("brief.category.dream")}</option>
            <option value="schemat">{t("brief.category.pattern")}</option>
          </select>
        </div>
        <div className="flex items-end">
          <label className="flex items-center gap-3 cursor-pointer select-none pb-2">
            <input
              type="checkbox"
              checked={aggressiveSchema}
              disabled={disabled}
              onChange={(e) => onAggressiveSchemaChange(e.target.checked)}
              className="rounded border-white/20 bg-white/5 text-teal focus:ring-teal/40"
            />
            <span className="text-[13px] text-white/75 leading-tight">
              {t("brief.aggressive.title")}
              <span className="block text-[11px] text-white/35 mt-0.5">
                {t("brief.aggressive.hint")}{" "}
                <code className="text-teal/80">{t("brief.aggressive.code")}</code>{" "}
                {t("brief.aggressive.hint_after")}
              </span>
            </span>
          </label>
        </div>
      </div>

      <button
        type="submit"
        disabled={
          disabled || description.trim().split(/\s+/).filter(Boolean).length < 5 || overLimit
        }
        className="w-full py-3 rounded-lg bg-teal text-navy font-medium text-[14px] hover:bg-teal-light transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        {disabled ? t("brief.btn.running") : t("brief.btn.start")}
      </button>
    </form>
  );
}
