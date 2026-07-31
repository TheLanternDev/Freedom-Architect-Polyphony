"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorGrid() {
  const local = useExperience((s) =>
    s.activeFloor === "grid" ? s.localProgress : s.activeIndex > 5 ? 1 : 0,
  );
  const city = useRef<THREE.InstancedMesh>(null);
  const count = 120;
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const data = useMemo(
    () =>
      Array.from({ length: count }, (_, i) => ({
        x: ((i % 12) - 5.5) * 2.2,
        z: -Math.floor(i / 12) * 3.5 - 2,
        h: 1 + ((i * 17) % 11) * 0.55,
        hue: i % 2,
      })),
    [],
  );

  useFrame((state) => {
    if (!city.current) return;
    const t = state.clock.elapsedTime;
    const rush = local * 40;
    data.forEach((d, i) => {
      dummy.position.set(d.x, d.h / 2, d.z + rush);
      if (dummy.position.z > 8) dummy.position.z = ((dummy.position.z + 40) % 40) - 32;
      dummy.scale.set(1, d.h * (0.6 + local * 0.8), 1);
      dummy.rotation.y = Math.sin(t * 0.2 + i) * 0.02;
      dummy.updateMatrix();
      city.current!.setMatrixAt(i, dummy.matrix);
    });
    city.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <FloorShell id="grid">
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, -10]}>
        <planeGeometry args={[80, 120]} />
        <meshStandardMaterial
          color="#080816"
          metalness={0.7}
          roughness={0.2}
          emissive="#15153a"
          emissiveIntensity={0.3}
        />
      </mesh>
      {/* neon road lines */}
      {Array.from({ length: 20 }).map((_, i) => (
        <mesh key={i} position={[0, 0.02, 6 - i * 3 - local * 30]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[0.15, 1.5]} />
          <meshBasicMaterial color="#00f0ff" transparent opacity={0.8} />
        </mesh>
      ))}
      <instancedMesh ref={city} args={[undefined, undefined, count]}>
        <boxGeometry />
        <meshStandardMaterial
          color="#101028"
          metalness={0.5}
          roughness={0.35}
          emissive="#ff2bd6"
          emissiveIntensity={0.25 + local * 0.5}
        />
      </instancedMesh>
      <GPUPoints
        count={4000}
        color="#00f0ff"
        size={0.03}
        spread={25}
        mode="stars"
        scrollDrive={local}
        speed={0.5}
      />
      {/* floating signage planes */}
      {Array.from({ length: 7 }).map((_, i) => (
        <mesh
          key={`sign-${i}`}
          position={[(i % 2 === 0 ? -1 : 1) * 4, 2 + (i % 3), -i * 4]}
        >
          <planeGeometry args={[1.6, 0.4]} />
          <meshBasicMaterial
            color={i % 2 ? "#ff2bd6" : "#2b6fff"}
            transparent
            opacity={0.7}
            side={THREE.DoubleSide}
          />
        </mesh>
      ))}
      <pointLight color="#ff2bd6" intensity={5} position={[-3, 4, 2]} distance={25} />
      <pointLight color="#00f0ff" intensity={5} position={[3, 3, 0]} distance={25} />
      <pointLight color="#2b6fff" intensity={3} position={[0, 6, -10]} distance={40} />
      <ambientLight intensity={0.12} />
    </FloorShell>
  );
}
