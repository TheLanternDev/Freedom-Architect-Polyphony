"use client";

import { useFrame } from "@react-three/fiber";
import { MeshTransmissionMaterial } from "@react-three/drei";
import { useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorBloom() {
  const local = useExperience((s) =>
    s.activeFloor === "bloom" ? s.localProgress : s.activeIndex > 3 ? 1 : 0,
  );
  const core = useRef<THREE.Group>(null);

  useFrame((state) => {
    if (!core.current) return;
    core.current.rotation.y = state.clock.elapsedTime * 0.15;
    core.current.scale.setScalar(0.7 + local * 1.1);
  });

  return (
    <FloorShell id="bloom">
      <mesh position={[0, 0, -18]}>
        <sphereGeometry args={[28, 32, 32]} />
        <meshBasicMaterial color="#06140c" side={THREE.BackSide} />
      </mesh>
      <GPUPoints
        count={4500}
        color="#7dffb3"
        size={0.045}
        spread={16}
        mode="spores"
        scrollDrive={local}
        speed={0.4}
      />
      <group ref={core} position={[0, 1.2, 0]}>
        {Array.from({ length: 9 }).map((_, i) => (
          <mesh
            key={i}
            position={[
              Math.cos((i / 9) * Math.PI * 2) * 1.4,
              Math.sin(i * 1.7) * 0.6,
              Math.sin((i / 9) * Math.PI * 2) * 1.4,
            ]}
            rotation={[i * 0.4, i * 0.7, 0]}
          >
            <icosahedronGeometry args={[0.45 + (i % 3) * 0.12, 1]} />
            <MeshTransmissionMaterial
              backside
              samples={4}
              thickness={0.6}
              chromaticAberration={0.25}
              anisotropy={0.3}
              distortion={0.4}
              distortionScale={0.4}
              temporalDistortion={0.15}
              color="#7dffb3"
            />
          </mesh>
        ))}
        <mesh>
          <sphereGeometry args={[0.55, 32, 32]} />
          <meshStandardMaterial
            color="#b8ff6a"
            emissive="#b8ff6a"
            emissiveIntensity={1.5 + local * 2}
            toneMapped={false}
          />
        </mesh>
      </group>
      {/* vine curves as tubes */}
      {Array.from({ length: 10 }).map((_, i) => (
        <Vine key={i} index={i} progress={local} />
      ))}
      <pointLight color="#7dffb3" intensity={5 + local * 6} distance={25} />
      <pointLight color="#b8ff6a" intensity={2} position={[3, 2, 2]} distance={15} />
      <ambientLight intensity={0.2} />
    </FloorShell>
  );
}

function Vine({ index, progress }: { index: number; progress: number }) {
  const ref = useRef<THREE.Mesh>(null);
  const curve = useRef(
    new THREE.CatmullRomCurve3(
      Array.from({ length: 6 }, (_, j) => {
        const a = (index / 10) * Math.PI * 2;
        return new THREE.Vector3(
          Math.cos(a + j * 0.3) * (1.5 + j * 0.4),
          j * 0.7 - 1,
          Math.sin(a + j * 0.3) * (1.5 + j * 0.4),
        );
      }),
    ),
  );

  useFrame((state) => {
    if (!ref.current) return;
    ref.current.rotation.y = state.clock.elapsedTime * 0.1 + index;
    const s = 0.8 + progress * 0.6;
    ref.current.scale.set(s, s, s);
  });

  return (
    <mesh ref={ref}>
      <tubeGeometry args={[curve.current, 64, 0.04, 8, false]} />
      <meshStandardMaterial
        color="#2d6b4a"
        emissive="#7dffb3"
        emissiveIntensity={0.3 + progress * 0.5}
        roughness={0.4}
      />
    </mesh>
  );
}
