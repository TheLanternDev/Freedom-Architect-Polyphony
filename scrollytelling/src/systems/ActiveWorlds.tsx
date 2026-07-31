"use client";

import { FLOORS } from "@/lib/floors";
import { useExperience } from "@/store/experienceStore";
import { WORLD_REGISTRY } from "@/systems/WorldRegistry";
import { Suspense } from "react";

/** Renders active floor ±1 for performance (LOD by section). */
export function ActiveWorlds() {
  const activeIndex = useExperience((s) => s.activeIndex);

  return (
    <>
      {FLOORS.map((floor, i) => {
        if (Math.abs(i - activeIndex) > 1) return null;
        const Comp = WORLD_REGISTRY[floor.id];
        return (
          <Suspense key={floor.id} fallback={null}>
            <Comp />
          </Suspense>
        );
      })}
    </>
  );
}
