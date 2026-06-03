import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  FileText,
  GitBranch,
  Paperclip,
  Sparkles,
  Sun,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import { useLang } from "@/lib/i18n";
import { isCouncilFa2 } from "@/config/product";
import { FragmentCompass } from "@/components/FragmentCompass";
import { FadeIn } from "@/components/ui/FadeIn";
import type { Brief } from "@/types/debate";
import { VoiceBriefButton } from "@/components/VoiceBriefButton";
import { getApiBase } from "@/lib/apiBase";
import { getApiAuthHeaders } from "@/lib/apiAuth";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";

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

function tplPreview(text: string, max = 88): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  return oneLine.length > max ? `${oneLine.slice(0, max - 1)}…` : oneLine;
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
  const [showOnboard, setShowOnboard] = useState(() => {
    try {
      return !window.localStorage.getItem(ONBOARD_KEY);
    } catch {
      return true;
    }
  });
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [attachNote, setAttachNote] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);

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
  const wordCount = description.trim().split(/\s+/).filter(Boolean).length;
  const canSubmit = !disabled && wordCount >= 5 && !overLimit;
  const charPct = MAX_LEN > 0 ? Math.min(charCount / MAX_LEN, 1) : 0;
  const charWarn = charPct >= 0.85 && !overLimit;
  const charsRemaining = MAX_LEN - charCount;

  const templates = useMemo(
    () =>
      [
        {
          labelKey: "brief.tpl.quit.label",
          descKey: "brief.tpl.quit",
          mode: "pelna" as const,
          category: "decyzja" as const,
          icon: FileText,
        },
        {
          labelKey: "brief.tpl.dream.label",
          descKey: "brief.tpl.dream",
          mode: "marzen" as const,
          category: "marzenie" as const,
          icon: Sparkles,
        },
        {
          labelKey: "brief.tpl.pattern.label",
          descKey: "brief.tpl.pattern",
          mode: "schematy" as const,
          category: "schemat" as const,
          icon: GitBranch,
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
    setSelectedTemplate(descKey);
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
    e.target.value = "";
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
    setAttachNote(
      skipped.length ? t("brief.attach.unsupported") + skipped.join(", ") : "",
    );
  }

  function removeAttachment(idx: number) {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
    setAttachNote("");
  }

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
    if (!canSubmit) return;
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

  const visibleTemplates = templates.filter(
    (tpl) => !allowedModes?.length || allowedModes.includes(tpl.mode),
  );

  const [showAdvanced, setShowAdvanced] = useState(false);

  // Mode picker — przeniesiony z sidebar (Krok 1 redesignu)
  const fa2 = isCouncilFa2();
  const ALL_MODES: { id: NonNullable<Brief["mode"]>; key: string; icon: LucideIcon }[] = [
    { id: "codzienny", key: "daily",    icon: Sun      },
    { id: "pelna",     key: "full",     icon: Users    },
    { id: "schematy",  key: "patterns", icon: GitBranch },
    { id: "marzen",    key: "dreams",   icon: Sparkles  },
  ];
  const visibleModes = ALL_MODES.filter(
    (m) => !allowedModes?.length || allowedModes.includes(m.id),
  );

  const submitLabel = (() => {
    const effectiveMode = aggressiveSchema ? "schematy" : selectedMode;
    if (fa2) return t("brief.btn.start_fa2") || "Zwołaj Radę Analityczną";
    if (effectiveMode === "schematy") return t("brief.btn.start_schematy") || "Konfrontuj schemat";
    if (effectiveMode === "codzienny") return t("brief.btn.start_codzienny") || "Zwołaj Radę";
    return t("brief.btn.start") || "Zwołaj Radę";
  })();

  return (
    <form onSubmit={handleSubmit} className="space-y-10 pb-4">
      <FadeIn>
        <header className="space-y-3">
          <span className="aw-council-seal">
            <Icon icon={Users} size="sm" className="opacity-80" />
            {t("app.workspace.seal")}
          </span>
          <h2 className="font-display text-display-lg text-text-primary tracking-display">
            {t("brief.hero.title")}
          </h2>
          <p className="aw-body max-w-2xl">{t("brief.hero.subtitle")}</p>
        </header>
      </FadeIn>

      {showOnboard && (
        <FadeIn delay={0.05}>
          <div className="rounded-card border border-teal/20 bg-teal-dim/50 px-5 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="aw-eyebrow text-teal-light mb-1.5">
              {t("brief.onboarding.title")}
            </p>
            <p className="text-[13px] text-text-secondary leading-relaxed">
              {t("brief.onboarding.body")}
            </p>
          </div>
          <button
            type="button"
            onClick={dismissOnboarding}
            className="no-print shrink-0 aw-btn-secondary text-[12px]"
          >
            {t("brief.onboarding.dismiss")}
          </button>
        </div>
        </FadeIn>
      )}

      {/* Gotowe briefy */}
      {visibleTemplates.length > 0 && (
        <FadeIn delay={0.08}>
        <section>
          <p className="aw-eyebrow mb-4 text-text-tertiary">
            {t("brief.quick.title")}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {visibleTemplates.map((tpl, i) => (
              <FadeIn key={tpl.labelKey} delay={0.1 + i * 0.05} y={6}>
              <button
                type="button"
                disabled={disabled}
                onClick={() =>
                  applyTemplate(tpl.descKey, tpl.mode, tpl.category)
                }
                className={cn(
                  "group aw-template-card w-full",
                  selectedTemplate === tpl.descKey && "is-selected",
                )}
              >
                <span className="flex items-center gap-2 mb-2">
                  <span
                    className={cn(
                      "flex items-center justify-center w-7 h-7 rounded-control border border-border bg-surface text-text-tertiary transition-colors duration-premium",
                      "group-hover:border-[var(--aw-accent-border)] group-hover:text-[var(--aw-accent-light)]",
                      selectedTemplate === tpl.descKey &&
                        "border-[var(--aw-accent-border)] text-[var(--aw-accent-light)] bg-[var(--aw-accent-dim)]",
                    )}
                  >
                    <Icon icon={tpl.icon} size="sm" />
                  </span>
                  <span className="text-[15px] font-medium text-text-primary">
                    {t(tpl.labelKey)}
                  </span>
                </span>
                <span className="block text-[13px] text-text-secondary leading-relaxed line-clamp-2">
                  {tplPreview(t(tpl.descKey))}
                </span>
              </button>
              </FadeIn>
            ))}
          </div>
        </section>
        </FadeIn>
      )}

      {/* Tryb debaty — pills (przeniesione z sidebar, Krok 1 redesignu) */}
      {visibleModes.length > 1 && (
        <FadeIn delay={0.10}>
        <section>
          <p className="aw-eyebrow mb-3 text-text-tertiary">
            {t(fa2 ? "mode.fa2.title" : "mode.title")}
          </p>
          <div className="flex flex-wrap gap-2">
            {visibleModes.map((m) => {
              const modeKey = fa2 ? `mode.fa2.${m.key}` : `mode.${m.key}`;
              const label = t(`${modeKey}.label`);
              const hint  = t(`${modeKey}.hint`);
              const active = selectedMode === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  disabled={disabled}
                  title={hint}
                  onClick={() => {
                    onModeChange?.(m.id);
                    setSelectedTemplate(null);
                  }}
                  className={cn(
                    "flex items-center gap-2 px-3 py-2 rounded-control border text-[12px] font-medium transition-all duration-premium",
                    active
                      ? "border-teal/35 bg-teal-dim text-teal-light"
                      : "border-border text-text-secondary hover:border-text-tertiary/30 hover:text-text-primary",
                    disabled && "opacity-40 cursor-not-allowed pointer-events-none",
                  )}
                >
                  <Icon icon={m.icon} size="sm" aria-hidden />
                  {label}
                </button>
              );
            })}
          </div>
        </section>
        </FadeIn>
      )}

      {/* Brief dla Rady — dokument roboczy */}
      <FadeIn delay={0.12}>
      <section className="aw-brief-panel">
        <div
          className={cn(
            "aw-brief-panel-inner",
            overLimit && "is-overlimit",
          )}
        >
          <div className="flex flex-wrap items-center gap-3 px-5 py-3.5 border-b border-border bg-surface/80">
            <span className="aw-eyebrow shrink-0">{t("brief.label")}</span>
            {/* Pola opcjonalne — zwinięte domyślnie (Krok 4 redesignu) */}
            <button
              type="button"
              onClick={() => setShowAdvanced((v) => !v)}
              className="ml-auto text-[11px] text-text-tertiary hover:text-text-secondary transition-colors flex items-center gap-1"
            >
              {showAdvanced ? t("brief.advanced.hide") || "Mniej opcji" : t("brief.advanced.show") || "Więcej opcji"}
              <Icon
                icon={ArrowRight}
                size="sm"
                className={cn("transition-transform duration-150", showAdvanced ? "-rotate-90" : "rotate-90")}
              />
            </button>
            {showAdvanced && (
              <div className="w-full flex flex-wrap items-center gap-3 pt-1">
                <label className="flex items-center gap-2">
                  <span className="text-[11px] text-text-tertiary uppercase tracking-wide-label">
                    {t("brief.category")}
                  </span>
                  <select
                    value={category}
                    onChange={(e) => {
                      setCategory(e.target.value as Brief["category"]);
                      setSelectedTemplate(null);
                    }}
                    disabled={disabled}
                    className="aw-select"
                  >
                    <option value="decyzja">{t("brief.category.decision")}</option>
                    <option value="projekt">{t("brief.category.project")}</option>
                    <option value="marzenie">{t("brief.category.dream")}</option>
                    <option value="schemat">{t("brief.category.pattern")}</option>
                  </select>
                </label>
                <label
                  className={cn(
                    "aw-toggle",
                    aggressiveSchema
                      ? "border-amber-500/40 bg-amber-950/25"
                      : "border-border hover:border-text-tertiary/30",
                    disabled && "opacity-40 cursor-not-allowed",
                  )}
                >
                  <span
                    className={cn(
                      "aw-toggle-track",
                      aggressiveSchema
                        ? "bg-amber-500/30 border-amber-500/50"
                        : "bg-surface border-border",
                    )}
                  >
                    <input
                      type="checkbox"
                      checked={aggressiveSchema}
                      disabled={disabled}
                      onChange={(e) => onAggressiveSchemaChange(e.target.checked)}
                      className="sr-only"
                    />
                    <span
                      className={cn(
                        "aw-toggle-thumb bg-text-secondary",
                        aggressiveSchema ? "left-[17px] bg-amber-200" : "left-[2px]",
                      )}
                    />
                  </span>
                  <span className="text-[11px] text-text-secondary leading-tight">
                    {t("brief.aggressive.title")}
                  </span>
                </label>
              </div>
            )}
          </div>

          <textarea
            value={description}
            onChange={(e) => {
              setDescription(e.target.value);
              setSelectedTemplate(null);
            }}
            disabled={disabled}
            placeholder={t("brief.placeholder")}
            rows={8}
            aria-describedby="brief-char-meter brief-min-words"
            className="aw-brief-textarea"
          />

          <div className="flex flex-wrap items-center gap-3 px-5 py-3.5 border-t border-border bg-surface/60">
            <label className={cn("aw-attach-btn", disabled && "opacity-35 pointer-events-none")}>
              <input
                type="file"
                multiple
                accept=".txt,.md,.csv,.json,.log,.text,.pdf,.docx,text/*,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                disabled={disabled}
                onChange={handleFiles}
                className="hidden"
              />
              <Icon icon={Paperclip} size="sm" />
              {t("brief.attach.btn")}
            </label>

            <VoiceBriefButton
              disabled={disabled}
              lang={lang}
              onTranscript={(said) => {
                setDescription((prev) => (prev ? `${prev} ${said}` : said));
                setSelectedTemplate(null);
              }}
              labelIdle={t("brief.voice.idle")}
              labelListening={t("brief.voice.active")}
              unsupportedHint={t("brief.voice.unsupported")}
            />

            <span className="hidden sm:inline text-[11px] text-text-tertiary ml-1">
              {t("brief.attach.hint")}
            </span>

            <div id="brief-char-meter" className="aw-char-meter">
              <span
                className={cn(
                  "text-[11px] tabular-nums font-mono",
                  overLimit ? "text-red-400" : charWarn ? "text-amber-300" : "text-text-tertiary",
                )}
              >
                {charCount.toLocaleString()} / {MAX_LEN.toLocaleString()}
              </span>
              <div className="aw-char-meter-bar" aria-hidden>
                <div
                  className={cn(
                    "aw-char-meter-fill",
                    overLimit && "is-over",
                    charWarn && "is-warn",
                  )}
                  style={{ width: `${Math.min(charPct * 100, 100)}%` }}
                />
              </div>
              {!overLimit && charCount > 0 && (
                <span className="text-[10px] text-text-tertiary/80">
                  {charsRemaining.toLocaleString()} {t("brief.chars.remaining")}
                </span>
              )}
            </div>
          </div>

          {attachments.length > 0 && (
            <ul className="px-5 pb-4 pt-1 space-y-1.5 border-t border-border/60">
              {attachments.map((a, i) => (
                <li key={`${a.name}-${i}`} className="aw-attach-chip">
                  <span className="truncate text-text-secondary">
                    {a.name}{" "}
                    <span className="text-text-tertiary font-mono text-[10px]">
                      ({a.content.length.toLocaleString()})
                    </span>
                  </span>
                  <button
                    type="button"
                    onClick={() => removeAttachment(i)}
                    disabled={disabled}
                    className="aw-attach-chip-remove"
                    aria-label={t("brief.attach.remove")}
                  >
                    <Icon icon={X} size="sm" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <p
          id="brief-min-words"
          className={cn(
            "text-[11px] mt-2 px-1 transition-colors duration-premium",
            wordCount > 0 && wordCount < 5 ? "text-amber-300/90" : "text-text-tertiary/70",
          )}
        >
          {wordCount < 5 ? t("brief.chars.min_words") : "\u00A0"}
        </p>

        {attachNote && (
          <p className="text-[11px] text-amber-400/85 mt-2 px-1">{attachNote}</p>
        )}

        {aggressiveSchema && (
          <p className="aw-caption mt-3 px-1">
            {t("brief.aggressive.hint")}{" "}
            <code className="text-teal-light">{t("brief.aggressive.code")}</code>{" "}
            {t("brief.aggressive.hint_after")}
          </p>
        )}
      </section>
      </FadeIn>

      {/* Sticky action bar — FragmentCompass jako ambient indicator (AKSJOMAT 0) */}
      <div className="aw-action-bar">
        <div className="aw-action-bar-inner">
          {/* Kompas Fragmentu — inline, nie floating (Krok 4 redesignu) */}
          <div className="hidden sm:block shrink-0">
            <FragmentCompass compact />
          </div>
          <div className="hidden sm:block min-w-0 flex-1">
            {disabled ? (
              <p className="text-[12px] text-teal-light flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-teal-light animate-pulse shrink-0" />
                {t("brief.btn.running")}
              </p>
            ) : (
              <p className="text-[12px] text-text-tertiary">
                {wordCount >= 5 ? " " : t("brief.chars.min_words")}
              </p>
            )}
          </div>
          <button
            type="submit"
            disabled={!canSubmit}
            className={cn(
              "aw-btn-primary px-8 py-3 text-[14px]",
              "inline-flex items-center gap-2 w-full sm:w-auto justify-center",
              disabled && "aw-btn-running",
              canSubmit && "shadow-[var(--aw-accent-glow)]",
            )}
          >
            {disabled ? (
              <>
                <span className="w-1.5 h-1.5 rounded-full bg-app/60 animate-pulse" />
                {t("brief.btn.running")}
              </>
            ) : canSubmit ? (
              <>
                {submitLabel}
                <Icon icon={ArrowRight} size="sm" className="opacity-70" />
              </>
            ) : (
              submitLabel
            )}
          </button>
        </div>
      </div>
    </form>
  );
}
