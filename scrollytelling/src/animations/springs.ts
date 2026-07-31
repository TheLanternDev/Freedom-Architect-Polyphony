import * as THREE from "three";

/** Spring-ish critically damped follow for non-R3F values */
export function damp(current: number, target: number, lambda: number, dt: number) {
  return THREE.MathUtils.damp(current, target, lambda, dt);
}

export function cinematicPulse(t: number, local: number) {
  return 1 + Math.sin(t * 2.2) * 0.03 * Math.sin(local * Math.PI);
}
