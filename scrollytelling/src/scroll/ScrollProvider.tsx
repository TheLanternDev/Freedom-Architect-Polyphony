"use client";

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import Lenis from "lenis";
import { FLOORS, floorLocalProgress, floorRanges, TOTAL_VH } from "@/lib/floors";
import { useExperience } from "@/store/experienceStore";

type ScrollApi = { lenis: Lenis | null; totalVh: number };

const ScrollCtx = createContext<ScrollApi>({ lenis: null, totalVh: TOTAL_VH });

export function useScrollApi() {
  return useContext(ScrollCtx);
}

export function ScrollProvider({ children }: { children: ReactNode }) {
  const lenisRef = useRef<Lenis | null>(null);
  const ranges = useRef(floorRanges());
  const lastP = useRef(0);
  const lastT = useRef(performance.now());

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    useExperience.getState().setReducedMotion(reduced);

    const lenis = new Lenis({
      duration: reduced ? 0.4 : 1.35,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      smoothWheel: !reduced,
      touchMultiplier: 1.35,
    });
    lenisRef.current = lenis;

    let raf = 0;
    const frame = (time: number) => {
      lenis.raf(time);
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    const onScroll = ({ progress }: { progress: number }) => {
      const now = performance.now();
      const dt = Math.max(0.001, (now - lastT.current) / 1000);
      const velocity = (progress - lastP.current) / dt;
      lastP.current = progress;
      lastT.current = now;
      useExperience.getState().setProgress(progress, velocity);

      const r = ranges.current;
      let active = r[0];
      for (const range of r) {
        if (progress >= range.start && progress < range.end) {
          active = range;
          break;
        }
        if (progress >= range.end) active = range;
      }
      const local = floorLocalProgress(progress, active.start, active.end);
      const floor = FLOORS.find((f) => f.id === active.id)!;
      useExperience.getState().setActive(active.id, floor.index, local);
    };

    lenis.on("scroll", onScroll);
    onScroll({ progress: 0 });

    const onPointer = (e: PointerEvent) => {
      const nx = (e.clientX / window.innerWidth) * 2 - 1;
      const ny = -(e.clientY / window.innerHeight) * 2 + 1;
      useExperience.getState().setPointer({
        x: e.clientX,
        y: e.clientY,
        nx,
        ny,
      });
    };
    window.addEventListener("pointermove", onPointer, { passive: true });

    return () => {
      cancelAnimationFrame(raf);
      lenis.destroy();
      window.removeEventListener("pointermove", onPointer);
    };
  }, []);

  return (
    <ScrollCtx.Provider value={{ lenis: lenisRef.current, totalVh: TOTAL_VH }}>
      {children}
    </ScrollCtx.Provider>
  );
}
