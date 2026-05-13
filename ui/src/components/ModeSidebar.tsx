import { useLang } from "@/lib/i18n";
import type { Brief } from "@/types/debate";

const MODE_IDS: { id: NonNullable<Brief["mode"]>; key: string }[] = [
  { id: "marzen", key: "dreams" },
  { id: "codzienny", key: "daily" },
  { id: "schematy", key: "patterns" },
  { id: "pelna", key: "full" },
];

interface Props {
  selected: Brief["mode"];
  onChange: (m: Brief["mode"]) => void;
  disabled: boolean;
}

export function ModeSidebar({ selected, onChange, disabled }: Props) {
  const { t } = useLang();
  return (
    <nav className="space-y-1">
      <p className="text-[10px] uppercase tracking-widest text-white/35 px-2 mb-2">
        {t("mode.title")}
      </p>
      {MODE_IDS.map(({ id, key }) => {
        const active = selected === id;
        const label = t(`mode.${key}.label`);
        const hint = t(`mode.${key}.hint`);
        return (
          <button
            key={id}
            type="button"
            disabled={disabled}
            onClick={() => onChange(id)}
            title={hint}
            className={`
              w-full text-left rounded-lg px-3 py-2.5 transition-colors border
              ${active ? "border-teal/50 bg-teal/10 text-teal-light" : "border-transparent text-white/60 hover:bg-white/[0.04] hover:text-white/85"}
              ${disabled ? "opacity-40 cursor-not-allowed" : ""}
            `}
          >
            <span className="block text-[13px] font-medium">{label}</span>
            <span className="block text-[10px] text-white/35 mt-0.5 leading-snug">
              {hint}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
