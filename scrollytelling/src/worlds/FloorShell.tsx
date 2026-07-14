"use client";

import type { FloorId } from "@/lib/floors";
import { FLOORS } from "@/lib/floors";
import { useExperience } from "@/store/experienceStore";
import { useFrame } from "@react-three/fiber";
import { useRef, type ReactNode } from "react";
import * as THREE from "three";

type Props = { id: FloorId; children: ReactNode };

/** Activates fog + visibility for ±1 floors; parallax root for depth planes */
export function FloorShell({ id, children }: Props) {
  const group = useRef<THREE.Group>(null);
  const def = FLOORS.find((f) => f.id === id)!;
  const offsetY = -def.index * 0.01; // identity layered, camera teleports by scroll

  useFrame((state) => {
    const { activeIndex, pointer, localProgress, activeFloor } =
      useExperience.getState();
    const dist = Math.abs(activeIndex - def.index);
    if (!group.current) return;
    group.current.visible = dist <= 1;
    if (dist > 1) return;

    // subtle world sway + scroll-linked breathing
    const live = activeFloor === id ? localProgress : activeIndex > def.index ? 1 : 0;
    group.current.position.x = pointer.nx * 0.15 * (1 - dist);
    group.current.position.y = offsetY + Math.sin(state.clock.elapsedTime * 0.3 + def.index) * 0.05;
    group.current.rotation.y = pointer.nx * 0.03;
    group.current.rotation.x = -pointer.ny * 0.02;

    if (activeFloor === id) {
      state.scene.fog = new THREE.FogExp2(def.palette.fog, def.fogDensity);
      state.scene.background = new THREE.Color(def.palette.bg);
    }

    // depth scale pulse on narrative climax mid-floor
    const pulse = 1 + Math.sin(live * Math.PI) * 0.02;
    group.current.scale.setScalar(pulse);
  });

  return <group ref={group}>{children}</group>;
}
