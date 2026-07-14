"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { MonolithDebris } from "@/physics/MonolithDebris";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorMonolith() {
  const local = useExperience((s) =>
    s.activeFloor === "monolith" ? s.localProgress : s.activeIndex > 2 ? 1 : 0,
  );
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const count = 48;

  const dummy = useMemo(() => new THREE.Object3D(), []);
  const bases = useMemo(() => {
    return Array.from({ length: count }, (_, i) => {
      const a = (i / count) * Math.PI * 2;
      const r = 3 + (i % 5) * 1.4;
      return {
        x: Math.cos(a) * r,
        z: Math.sin(a) * r,
        h: 2 + (i % 7) * 1.35,
        phase: Math.random() * Math.PI * 2,
      };
    });
  }, []);

  useFrame((state) => {
    if (!meshRef.current) return;
    const t = state.clock.elapsedTime;
    bases.forEach((b, i) => {
      const rise = Math.min(1, local * 1.4 + (i % 5) * 0.05);
      dummy.position.set(b.x, (b.h * rise) / 2, b.z);
      dummy.scale.set(0.7 + (i % 3) * 0.2, b.h * rise, 0.7 + (i % 2) * 0.25);
      dummy.rotation.set(0, b.phase + t * 0.02, Math.sin(t * 0.3 + b.phase) * 0.02);
      dummy.updateMatrix();
      meshRef.current!.setMatrixAt(i, dummy.matrix);
    });
    meshRef.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <FloorShell id="monolith">
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <circleGeometry args={[40, 64]} />
        <meshStandardMaterial color="#1a1612" roughness={0.95} metalness={0.05} />
      </mesh>
      <instancedMesh ref={meshRef} args={[undefined, undefined, count]} castShadow>
        <boxGeometry args={[1, 1, 1]} />
        <meshStandardMaterial
          color="#3a3228"
          roughness={0.7}
          metalness={0.15}
          emissive="#c4a574"
          emissiveIntensity={0.05 + local * 0.15}
        />
      </instancedMesh>
      {/* central judgment slab */}
      <mesh position={[0, 3 + local * 4, 0]} castShadow>
        <boxGeometry args={[2.2, 8, 0.4]} />
        <meshStandardMaterial color="#2a241c" metalness={0.4} roughness={0.4} />
      </mesh>
      <GPUPoints
        count={3500}
        color="#c4a574"
        size={0.025}
        spread={20}
        mode="dust"
        scrollDrive={local}
        speed={0.15}
      />
      {/* floating rune discs */}
      {Array.from({ length: 8 }).map((_, i) => (
        <mesh
          key={i}
          position={[
            Math.cos(i) * 5,
            2 + i * 0.6 + local * 2,
            Math.sin(i) * 5,
          ]}
          rotation={[Math.PI / 2, 0, i]}
        >
          <torusGeometry args={[0.6, 0.03, 8, 48]} />
          <meshBasicMaterial color="#e8d5a8" transparent opacity={0.35 + local * 0.3} />
        </mesh>
      ))}
      <directionalLight
        castShadow
        position={[8, 16, 6]}
        intensity={1.4 + local}
        color="#e8d5a8"
        shadow-mapSize={[1024, 1024]}
      />
      <ambientLight intensity={0.25} />
      <hemisphereLight args={["#4a3f32", "#0c0b0a", 0.4]} />
      <MonolithDebris />
    </FloorShell>
  );
}
