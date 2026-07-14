"use client";

import { create } from "zustand";
import type { FloorId } from "@/lib/floors";

type Pointer = { x: number; y: number; nx: number; ny: number };

type ExperienceState = {
  progress: number;
  velocity: number;
  activeFloor: FloorId;
  activeIndex: number;
  localProgress: number;
  pointer: Pointer;
  ready: boolean;
  reducedMotion: boolean;
  setProgress: (p: number, v: number) => void;
  setActive: (id: FloorId, index: number, local: number) => void;
  setPointer: (p: Pointer) => void;
  setReady: (r: boolean) => void;
  setReducedMotion: (r: boolean) => void;
};

export const useExperience = create<ExperienceState>((set) => ({
  progress: 0,
  velocity: 0,
  activeFloor: "null",
  activeIndex: 0,
  localProgress: 0,
  pointer: { x: 0, y: 0, nx: 0, ny: 0 },
  ready: false,
  reducedMotion: false,
  setProgress: (progress, velocity) => set({ progress, velocity }),
  setActive: (activeFloor, activeIndex, localProgress) =>
    set({ activeFloor, activeIndex, localProgress }),
  setPointer: (pointer) => set({ pointer }),
  setReady: (ready) => set({ ready }),
  setReducedMotion: (reducedMotion) => set({ reducedMotion }),
}));
