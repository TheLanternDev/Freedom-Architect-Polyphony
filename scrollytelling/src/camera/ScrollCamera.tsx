"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { FLOORS, floorRanges } from "@/lib/floors";
import { easeInOutCubic, lerpVec3 } from "@/lib/math";
import { useExperience } from "@/store/experienceStore";

/**
 * Spline-like camera across floor anchors. Scroll drives position & look-at.
 * Pointer adds parallax without breaking narrative path.
 */
export function ScrollCamera() {
  const look = useRef(new THREE.Vector3());
  const targetPos = useRef(new THREE.Vector3());
  const targetLook = useRef(new THREE.Vector3());
  const ranges = useMemo(() => floorRanges(), []);

  useFrame((state, delta) => {
    const { progress, pointer, reducedMotion } = useExperience.getState();
    const damp = reducedMotion ? 12 : 4.5;

    let pos: [number, number, number] = FLOORS[0].camera.start;
    let lookAt: [number, number, number] = FLOORS[0].camera.lookStart;

    for (let i = 0; i < ranges.length; i++) {
      const r = ranges[i];
      const f = FLOORS[i];
      if (progress >= r.start && progress <= r.end + 0.0001) {
        const t = easeInOutCubic(
          Math.min(1, Math.max(0, (progress - r.start) / (r.end - r.start))),
        );
        pos = lerpVec3(f.camera.start, f.camera.end, t);
        lookAt = lerpVec3(f.camera.lookStart, f.camera.lookEnd, t);
        break;
      }
    }

    const parallax = reducedMotion ? 0.05 : 0.35;
    targetPos.current.set(
      pos[0] + pointer.nx * parallax,
      pos[1] + pointer.ny * parallax * 0.4,
      pos[2],
    );
    targetLook.current.set(
      lookAt[0] + pointer.nx * 0.15,
      lookAt[1] + pointer.ny * 0.1,
      lookAt[2],
    );

    state.camera.position.lerp(targetPos.current, 1 - Math.exp(-damp * delta));
    look.current.lerp(targetLook.current, 1 - Math.exp(-damp * delta));
    state.camera.lookAt(look.current);
  });

  return null;
}
