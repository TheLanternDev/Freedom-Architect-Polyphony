import * as THREE from "three";

export function makeEmissive(
  color: string,
  intensity = 1,
): THREE.MeshStandardMaterial {
  return new THREE.MeshStandardMaterial({
    color,
    emissive: color,
    emissiveIntensity: intensity,
    toneMapped: false,
  });
}
