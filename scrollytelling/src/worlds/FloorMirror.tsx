"use client";

import { useFrame } from "@react-three/fiber";
import { MeshReflectorMaterial } from "@react-three/drei";
import { useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorMirror() {
  const local = useExperience((s) =>
    s.activeFloor === "mirror" ? s.localProgress : s.activeIndex > 7 ? 1 : 0,
  );
  const shards = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!shards.current) return;
    shards.current.rotation.y = state.clock.elapsedTime * 0.12;
    shards.current.children.forEach((c, i) => {
      c.rotation.x = state.clock.elapsedTime * (0.2 + i * 0.02) + local * i;
      c.position.y = Math.sin(state.clock.elapsedTime + i) * 0.3 * local;
    });
  });

  return (
    <FloorShell id="mirror">
      <mesh>
        <sphereGeometry args={[28, 24, 24]} />
        <meshBasicMaterial color="#0a0a12" side={THREE.BackSide} />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.5, 0]}>
        <circleGeometry args={[14, 64]} />
        <MeshReflectorMaterial
          blur={[300, 80]}
          resolution={512}
          mixBlur={0.8}
          mixStrength={1.6}
          roughness={0.15}
          depthScale={0.8}
          minDepthThreshold={0.4}
          maxDepthThreshold={1.4}
          color="#1c1c2e"
          metalness={0.9}
        />
      </mesh>
      <group ref={shards}>
        {Array.from({ length: 16 }).map((_, i) => {
          const a = (i / 16) * Math.PI * 2;
          return (
            <mesh
              key={i}
              position={[Math.cos(a) * 2.5, 0.8 + (i % 4) * 0.35, Math.sin(a) * 2.5]}
              rotation={[a, a * 0.5, 0]}
            >
              <planeGeometry args={[1.1, 1.6]} />
              <meshPhysicalMaterial
                color="#e2e8f0"
                metalness={1}
                roughness={0.05}
                transmission={0.55}
                thickness={0.4}
                transparent
                opacity={0.85}
                side={THREE.DoubleSide}
                emissive="#94a3b8"
                emissiveIntensity={0.15 + local * 0.4}
              />
            </mesh>
          );
        })}
      </group>
      {/* fractured ego core */}
      <mesh position={[0, 1, 0]}>
        <icosahedronGeometry args={[0.7, 0]} />
        <meshPhysicalMaterial
          color="#ffffff"
          metalness={1}
          roughness={0}
          transmission={0.3}
          emissive="#e2e8f0"
          emissiveIntensity={0.5 + local}
        />
      </mesh>
      <GPUPoints
        count={3500}
        color="#94a3b8"
        size={0.028}
        spread={16}
        mode="dust"
        scrollDrive={local}
        speed={0.2}
      />
      <pointLight color="#e2e8f0" intensity={5 + local * 4} distance={25} />
      <spotLight
        color="#64748b"
        intensity={8}
        position={[4, 8, 4]}
        angle={0.5}
        penumbra={0.6}
        castShadow
      />
      <ambientLight intensity={0.2} />
    </FloorShell>
  );
}
