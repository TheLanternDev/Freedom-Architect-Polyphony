/**
 * Tryb Marzeń — dedykowany multi-step wizard.
 * Prowadzi użytkownika przez: marzenie → filary → kamienie milowe → pierwszy krok.
 * Na koniec tworzy brief z category=marzenie, mode=marzen i uruchamia debatę.
 */
import { useCallback, useState } from "react";
import { useLang } from "@/lib/i18n";
import type { Brief } from "@/types/debate";

interface Props {
  onSubmit: (brief: Brief) => void;
  disabled: boolean;
  onClose: () => void;
}

const STEPS = ["dream", "pillars", "milestones", "first_step", "summary"] as const;
type Step = (typeof STEPS)[number];

export function DreamWizard({ onSubmit, disabled, onClose }: Props) {
  const { t } = useLang();
  const [step, setStep] = useState<Step>("dream");
  const [dream, setDream] = useState("");
  const [pillars, setPillars] = useState(["", "", ""]);
  const [milestones, setMilestones] = useState([
    { title: "", due: "" },
    { title: "", due: "" },
  ]);
  const [firstStep, setFirstStep] = useState("");

  const stepIdx = STEPS.indexOf(step);
  const canNext =
    step === "dream"
      ? dream.trim().length >= 20
      : step === "pillars"
        ? pillars.filter((p) => p.trim()).length >= 2
        : step === "milestones"
          ? milestones.some((m) => m.title.trim())
          : step === "first_step"
            ? firstStep.trim().length >= 10
            : true;

  const next = useCallback(() => {
    const idx = STEPS.indexOf(step);
    if (idx < STEPS.length - 1) setStep(STEPS[idx + 1]);
  }, [step]);

  const prev = useCallback(() => {
    const idx = STEPS.indexOf(step);
    if (idx > 0) setStep(STEPS[idx - 1]);
  }, [step]);

  const submit = useCallback(() => {
    const pillarList = pillars.filter((p) => p.trim());
    const milestoneList = milestones
      .filter((m) => m.title.trim())
      .map((m) => `${m.title}${m.due ? ` (do ${m.due})` : ""}`)
      .join("; ");

    const description = [
      `Marzenie: ${dream.trim()}`,
      `Filary: ${pillarList.join(", ")}`,
      milestoneList ? `Kamienie milowe: ${milestoneList}` : "",
      `Pierwszy krok (≤60 min): ${firstStep.trim()}`,
    ]
      .filter(Boolean)
      .join("\n\n");

    onSubmit({
      description,
      category: "marzenie",
      mode: "marzen",
    });
  }, [dream, pillars, milestones, firstStep, onSubmit]);

  const updatePillar = (idx: number, val: string) => {
    setPillars((prev) => prev.map((p, i) => (i === idx ? val : p)));
  };

  const updateMilestone = (idx: number, field: "title" | "due", val: string) => {
    setMilestones((prev) =>
      prev.map((m, i) => (i === idx ? { ...m, [field]: val } : m)),
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-2xl mx-4 rounded-2xl border border-teal/20 bg-navy/95 shadow-2xl overflow-hidden">
        {/* Progress bar */}
        <div className="h-1 bg-white/5">
          <div
            className="h-full bg-teal transition-all duration-500"
            style={{ width: `${((stepIdx + 1) / STEPS.length) * 100}%` }}
          />
        </div>

        <div className="p-6 space-y-5">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-[18px] font-medium text-white">
                {t("wizard.title")}
              </h2>
              <p className="text-[11px] text-white/40 mt-0.5">
                {t(`wizard.step.${step}`)} · {stepIdx + 1}/{STEPS.length}
              </p>
            </div>
            <button
              onClick={onClose}
              className="text-white/30 hover:text-white/70 text-sm"
            >
              {t("wizard.close")}
            </button>
          </div>

          {/* Step: Dream */}
          {step === "dream" && (
            <div className="space-y-3">
              <p className="text-[14px] text-white/70 leading-relaxed">
                {t("wizard.dream.prompt")}
              </p>
              <textarea
                value={dream}
                onChange={(e) => setDream(e.target.value)}
                placeholder={t("wizard.dream.placeholder")}
                rows={4}
                disabled={disabled}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-[14px] text-white placeholder:text-white/20 resize-none focus:outline-none focus:border-teal/60"
              />
            </div>
          )}

          {/* Step: Pillars */}
          {step === "pillars" && (
            <div className="space-y-3">
              <p className="text-[14px] text-white/70 leading-relaxed">
                {t("wizard.pillars.prompt")}
              </p>
              {pillars.map((p, i) => (
                <input
                  key={i}
                  value={p}
                  onChange={(e) => updatePillar(i, e.target.value)}
                  placeholder={`${t("wizard.pillars.pillar")} ${i + 1}`}
                  disabled={disabled}
                  className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-2.5 text-[13px] text-white placeholder:text-white/20 focus:outline-none focus:border-teal/60"
                />
              ))}
              <button
                type="button"
                onClick={() => setPillars([...pillars, ""])}
                className="text-[11px] text-teal/70 hover:text-teal transition-colors"
              >
                + {t("wizard.pillars.add")}
              </button>
            </div>
          )}

          {/* Step: Milestones */}
          {step === "milestones" && (
            <div className="space-y-3">
              <p className="text-[14px] text-white/70 leading-relaxed">
                {t("wizard.milestones.prompt")}
              </p>
              {milestones.map((m, i) => (
                <div key={i} className="flex gap-2">
                  <input
                    value={m.title}
                    onChange={(e) => updateMilestone(i, "title", e.target.value)}
                    placeholder={t("wizard.milestones.what")}
                    disabled={disabled}
                    className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[13px] text-white placeholder:text-white/20 focus:outline-none focus:border-teal/60"
                  />
                  <input
                    type="date"
                    value={m.due}
                    onChange={(e) => updateMilestone(i, "due", e.target.value)}
                    disabled={disabled}
                    className="w-[140px] bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-[12px] text-white/70 focus:outline-none focus:border-teal/60"
                  />
                </div>
              ))}
              <button
                type="button"
                onClick={() =>
                  setMilestones([...milestones, { title: "", due: "" }])
                }
                className="text-[11px] text-teal/70 hover:text-teal transition-colors"
              >
                + {t("wizard.milestones.add")}
              </button>
            </div>
          )}

          {/* Step: First step */}
          {step === "first_step" && (
            <div className="space-y-3">
              <p className="text-[14px] text-white/70 leading-relaxed">
                {t("wizard.first_step.prompt")}
              </p>
              <textarea
                value={firstStep}
                onChange={(e) => setFirstStep(e.target.value)}
                placeholder={t("wizard.first_step.placeholder")}
                rows={3}
                disabled={disabled}
                className="w-full bg-white/5 border border-white/10 rounded-lg px-4 py-3 text-[14px] text-white placeholder:text-white/20 resize-none focus:outline-none focus:border-teal/60"
              />
            </div>
          )}

          {/* Step: Summary */}
          {step === "summary" && (
            <div className="space-y-3">
              <p className="text-[14px] text-white/70 leading-relaxed">
                {t("wizard.summary.prompt")}
              </p>
              <div className="rounded-lg border border-white/10 bg-white/[0.02] p-4 space-y-3 text-[13px]">
                <div>
                  <span className="text-teal/80 text-[10px] uppercase tracking-widest">
                    {t("wizard.summary.dream")}
                  </span>
                  <p className="text-white/80 mt-0.5">{dream}</p>
                </div>
                <div>
                  <span className="text-teal/80 text-[10px] uppercase tracking-widest">
                    {t("wizard.summary.pillars")}
                  </span>
                  <p className="text-white/80 mt-0.5">
                    {pillars.filter((p) => p.trim()).join(" · ")}
                  </p>
                </div>
                {milestones.some((m) => m.title.trim()) && (
                  <div>
                    <span className="text-teal/80 text-[10px] uppercase tracking-widest">
                      {t("wizard.summary.milestones")}
                    </span>
                    <ul className="text-white/80 mt-0.5 space-y-1">
                      {milestones
                        .filter((m) => m.title.trim())
                        .map((m, i) => (
                          <li key={i}>
                            {m.title}
                            {m.due && (
                              <span className="text-white/40 ml-1">
                                → {m.due}
                              </span>
                            )}
                          </li>
                        ))}
                    </ul>
                  </div>
                )}
                <div>
                  <span className="text-teal/80 text-[10px] uppercase tracking-widest">
                    {t("wizard.summary.first_step")}
                  </span>
                  <p className="text-white/80 mt-0.5">{firstStep}</p>
                </div>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="flex justify-between pt-2">
            <button
              type="button"
              onClick={stepIdx === 0 ? onClose : prev}
              className="text-[12px] text-white/40 hover:text-white/70 transition-colors"
            >
              {stepIdx === 0 ? t("wizard.cancel") : t("wizard.back")}
            </button>
            {step === "summary" ? (
              <button
                type="button"
                onClick={submit}
                disabled={disabled}
                className="text-[13px] px-5 py-2 rounded-lg bg-teal text-navy font-medium hover:bg-teal-light transition-colors disabled:opacity-35"
              >
                {t("wizard.launch")}
              </button>
            ) : (
              <button
                type="button"
                onClick={next}
                disabled={!canNext}
                className="text-[12px] px-4 py-1.5 rounded-full bg-teal/15 border border-teal/40 text-teal hover:bg-teal/25 disabled:opacity-30 transition-colors"
              >
                {t("wizard.next")}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
