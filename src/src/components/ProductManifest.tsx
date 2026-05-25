import { useState } from "react";
import { useLang } from "@/lib/i18n";

export function ProductManifest() {
  const { t } = useLang();
  const [open, setOpen] = useState(false);
  return (
    <section className="rounded-xl border border-white/[0.07] bg-white/[0.02] px-4 py-3">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-left text-[12px] font-medium text-white/70 hover:text-teal-light transition-colors"
      >
        <span>{t("manifest.title")}</span>
        <span className="text-white/35 tabular-nums text-[11px]">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="mt-3 text-[12px] text-white/60 leading-relaxed whitespace-pre-wrap border-t border-white/[0.06] pt-3">
          {t("manifest.body")}
        </div>
      )}
    </section>
  );
}
