import {
  GitBranch,
  Sparkles,
  Sun,
  Users,
  type LucideIcon,
} from "lucide-react";
import { isCouncilFa2 } from "@/config/product";
import { useLang } from "@/lib/i18n";
import { cn } from "@/lib/cn";
import { Icon } from "@/components/ui/Icon";
import { SidebarSection } from "@/components/ui/SidebarSection";
import type { Brief } from "@/types/debate";

const FEATURED_ID: NonNullable<Brief["mode"]> = "pelna";

const COMPACT_MODES: { id: NonNullable<Brief["mode"]>; key: string; icon: LucideIcon }[] = [
  { id: "marzen", key: "dreams", icon: Sparkles },
  { id: "codzienny", key: "daily", icon: Sun },
  { id: "schematy", key: "patterns", icon: GitBranch },
];

interface Props {
  selected: Brief["mode"];
  onChange: (m: Brief["mode"]) => void;
  disabled: boolean;
  allowedModes?: string[];
}

function modeAllowed(id: string, allowedModes?: string[]): boolean {
  return !allowedModes?.length || allowedModes.includes(id);
}

export function ModeSidebar({ selected, onChange, disabled, allowedModes }: Props) {
  const { t } = useLang();
  const fa2 = isCouncilFa2();
  const modeKey = (k: string) => (fa2 ? `mode.fa2.${k}` : `mode.${k}`);

  const featuredAllowed = modeAllowed(FEATURED_ID, allowedModes);
  const compactVisible = COMPACT_MODES.filter(({ id }) =>
    modeAllowed(id, allowedModes),
  );

  const featuredActive = selected === FEATURED_ID;
  const featuredLabel = t(`${modeKey("full")}.label`);
  const featuredHint = t(`${modeKey("full")}.hint`);

  return (
    <nav className="space-y-5" aria-label={t(fa2 ? "mode.fa2.title" : "mode.title")}>
      {featuredAllowed && (
        <SidebarSection label={t(fa2 ? "mode.fa2.title" : "mode.title")}>
          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange(FEATURED_ID)}
            title={featuredHint}
            className={cn("aw-featured-mode", featuredActive && "is-active")}
          >
            <div className="flex items-start gap-3">
              <span className="aw-featured-mode-icon">
                <Icon icon={Users} size="md" />
              </span>
              <div className="min-w-0 pt-0.5">
                <span
                  className={cn(
                    "block text-[14px] font-medium leading-tight",
                    featuredActive ? "aw-accent-highlight" : "text-text-primary",
                  )}
                >
                  {featuredLabel}
                </span>
                <span className="block text-[11px] text-text-tertiary mt-1 leading-snug">
                  {featuredHint}
                </span>
              </div>
            </div>
          </button>
        </SidebarSection>
      )}

      {compactVisible.length > 0 && (
        <SidebarSection label={t("mode.compact_title")}>
          <ul className="space-y-0.5">
            {compactVisible.map(({ id, key, icon: ModeIcon }) => {
              const active = selected === id;
              const label = t(`${modeKey(key)}.label`);
              const hint = t(`${modeKey(key)}.hint`);
              return (
                <li key={id}>
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() => onChange(id)}
                    title={hint}
                    className={cn(
                      "group w-full flex items-center gap-2.5 text-left rounded-control px-2.5 py-2",
                      "transition-all duration-premium border active:scale-[0.99]",
                      active
                        ? "border-teal/35 bg-teal-dim text-teal-light"
                        : "border-transparent text-text-secondary hover:bg-white/[0.03] hover:text-text-primary",
                      "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-teal/40",
                      disabled && "opacity-40 cursor-not-allowed",
                    )}
                  >
                    <span
                      className={cn(
                        "flex items-center justify-center w-7 h-7 rounded-control shrink-0 transition-colors duration-premium",
                        active
                          ? "text-teal-light"
                          : "text-text-tertiary group-hover:text-text-secondary",
                      )}
                    >
                      <Icon icon={ModeIcon} size="sm" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-[13px] font-medium leading-none truncate">
                        {label}
                      </span>
                      <span className="block text-[10px] text-text-tertiary mt-1 truncate leading-snug">
                        {hint}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </SidebarSection>
      )}
    </nav>
  );
}
