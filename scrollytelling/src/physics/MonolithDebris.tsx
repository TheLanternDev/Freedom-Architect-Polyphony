"use client";

import { Physics, RigidBody } from "@react-three/rapier";
import { useExperience } from "@/store/experienceStore";

/** Ambient physics debris — only when monolith is near-active */
export function MonolithDebris() {
  const active = useExperience((s) => Math.abs(s.activeIndex - 2) <= 1);
  if (!active) return null;

  return (
    <Physics gravity={[0, -2.5, 0]} colliders={false}>
      <RigidBody type="fixed" colliders="cuboid" position={[0, -0.5, 0]}>
        <mesh visible={false}>
          <boxGeometry args={[40, 1, 40]} />
        </mesh>
      </RigidBody>
      {Array.from({ length: 10 }).map((_, i) => (
        <RigidBody
          key={i}
          colliders="ball"
          position={[(i - 5) * 0.8, 6 + i * 0.3, -1]}
          restitution={0.4}
          linearDamping={0.3}
        >
          <mesh castShadow>
            <dodecahedronGeometry args={[0.18, 0]} />
            <meshStandardMaterial color="#c4a574" metalness={0.5} roughness={0.4} />
          </mesh>
        </RigidBody>
      ))}
    </Physics>
  );
}
