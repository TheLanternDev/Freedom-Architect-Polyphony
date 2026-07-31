"use client";

import { FLOORS, TOTAL_VH } from "@/lib/floors";
import { useExperience } from "@/store/experienceStore";

export function ScrollSpacer() {
  return (
    <div
      className="pointer-events-none relative z-10"
      style={{ height: `${TOTAL_VH}vh` }}
      aria-hidden
    >
      {FLOORS.map((f) => (
        <section key={f.id} style={{ height: `${f.vh}vh` }} data-floor={f.id} />
      ))}
    </div>
  );
}

export function ExperienceHUD() {
  const progress = useExperience((s) => s.progress);
  const activeFloor = useExperience((s) => s.activeFloor);
  const ready = useExperience((s) => s.ready);
  const index = useExperience((s) => s.activeIndex);
  const floor = FLOORS[index];

  return (
    <>
      {!ready && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#020203]">
          <div className="h-px w-24 overflow-hidden bg-white/10">
            <div className="h-full w-1/2 animate-pulse bg-[#ff6b2c]" />
          </div>
        </div>
      )}
      <div className="pointer-events-none fixed inset-x-0 top-0 z-40 flex items-start justify-between p-6 mix-blend-difference">
        <p className="font-[family-name:var(--font-display)] text-sm tracking-[0.35em] text-white uppercase">
          Verge
        </p>
        <p className="font-[family-name:var(--font-mono)] text-[10px] tracking-widest text-white/70 uppercase">
          {String(index + 1).padStart(2, "0")} / 10 — {activeFloor}
        </p>
      </div>
      <div className="pointer-events-none fixed bottom-6 left-6 z-40 max-w-xs">
        <p className="font-[family-name:var(--font-mono)] text-[10px] leading-relaxed tracking-wide text-white/50">
          {floor?.event}
        </p>
      </div>
      <div className="pointer-events-none fixed right-6 bottom-6 z-40 h-28 w-px bg-white/15">
        <div
          className="w-full bg-[#ff6b2c] transition-[height] duration-150"
          style={{ height: `${progress * 100}%` }}
        />
      </div>
      <div className="pointer-events-none fixed bottom-6 left-1/2 z-40 -translate-x-1/2 font-[family-name:var(--font-mono)] text-[9px] tracking-[0.4em] text-white/35 uppercase">
        scroll to travel
      </div>
    </>
  );
}
