"use client";

import { FLOORS, floorLocalProgress, floorRanges, type FloorId } from "@/lib/floors";
import { useExperience } from "@/store/experienceStore";
import { useMemo } from "react";

export function useFloorProgress(id: FloorId) {
  const progress = useExperience((s) => s.progress);
  const ranges = useMemo(() => floorRanges(), []);
  const range = ranges.find((r) => r.id === id)!;
  const def = FLOORS.find((f) => f.id === id)!;
  const local = floorLocalProgress(progress, range.start, range.end);
  const active = useExperience((s) => s.activeFloor === id);
  return { local, active, def, range };
}

export function usePointerParallax(strength = 0.3) {
  const pointer = useExperience((s) => s.pointer);
  return {
    x: pointer.nx * strength,
    y: pointer.ny * strength * 0.5,
  };
}
