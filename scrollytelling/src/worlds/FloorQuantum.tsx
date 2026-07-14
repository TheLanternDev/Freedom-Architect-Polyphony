"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorQuantum() {
  const local = useExperience((s) =>
    s.activeFloor === "quantum" ? s.localProgress : s.activeIndex > 6 ? 1 : 0,
  );
  const lines = useRef<THREE.LineSegments>(null);
  const orbs = useRef<THREE.Group>(null);

  const lineGeo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const n = 80;
    const pos = new Float32Array(n * 2 * 3);
    for (let i = 0; i < n; i++) {
      const a = Math.random() * Math.PI * 2;
      const b = Math.random() * Math.PI * 2;
      const r = 1 + Math.random() * 4;
      pos[i * 6] = Math.cos(a) * r;
      pos[i * 6 + 1] = (Math.random() - 0.5) * 4;
      pos[i * 6 + 2] = Math.sin(a) * r;
      pos[i * 6 + 3] = Math.cos(b) * r * 0.7;
      pos[i * 6 + 4] = (Math.random() - 0.5) * 4;
      pos[i * 6 + 5] = Math.sin(b) * r * 0.7;
    }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    return g;
  }, []);

  useFrame((state) => {
    if (lines.current) {
      lines.current.rotation.y = state.clock.elapsedTime * 0.08 + local * 1.5;
      lines.current.rotation.x = Math.sin(state.clock.elapsedTime * 0.2) * 0.2;
      (lines.current.material as THREE.LineBasicMaterial).opacity =
        0.25 + local * 0.55;
    }
    if (orbs.current) {
      orbs.current.rotation.y = -state.clock.elapsedTime * 0.25;
      orbs.current.scale.setScalar(0.6 + local * 1.2);
    }
  });

  return (
    <FloorShell id="quantum">
      <mesh>
        <sphereGeometry args={[30, 24, 24]} />
        <meshBasicMaterial color="#04040c" side={THREE.BackSide} />
      </mesh>
      <GPUPoints
        count={7000}
        color="#a78bfa"
        size={0.035}
        spread={10}
        mode="quantum"
        scrollDrive={local}
        speed={0.55}
      />
      <GPUPoints
        count={3000}
        color="#38bdf8"
        size={0.025}
        spread={14}
        mode="stars"
        scrollDrive={local}
        speed={0.3}
      />
      <lineSegments ref={lines} geometry={lineGeo}>
        <lineBasicMaterial color="#f0abfc" transparent opacity={0.4} />
      </lineSegments>
      <group ref={orbs}>
        {Array.from({ length: 5 }).map((_, i) => (
          <mesh
            key={i}
            position={[
              Math.cos((i / 5) * Math.PI * 2) * 2.5,
              Math.sin(i) * 0.8,
              Math.sin((i / 5) * Math.PI * 2) * 2.5,
            ]}
          >
            <sphereGeometry args={[0.25 + i * 0.04, 16, 16]} />
            <meshStandardMaterial
              color="#a78bfa"
              emissive={i % 2 ? "#38bdf8" : "#f0abfc"}
              emissiveIntensity={1.2 + local}
              toneMapped={false}
            />
          </mesh>
        ))}
      </group>
      {/* probability wave plane */}
      <WaveField progress={local} />
      <pointLight color="#a78bfa" intensity={6} distance={30} />
      <pointLight color="#38bdf8" intensity={4} position={[2, 2, 2]} distance={20} />
      <ambientLight intensity={0.15} />
    </FloorShell>
  );
}

function WaveField({ progress }: { progress: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!ref.current) return;
    const pos = ref.current.geometry.attributes.position as THREE.BufferAttribute;
    const t = state.clock.elapsedTime;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const z =
        Math.sin(x * 1.5 + t * 2) * 0.25 * progress +
        Math.cos(y * 1.2 + t * 1.5) * 0.2;
      pos.setZ(i, z);
    }
    pos.needsUpdate = true;
    ref.current.geometry.computeVertexNormals();
  });
  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, -2, 0]}>
      <planeGeometry args={[12, 12, 48, 48]} />
      <meshStandardMaterial
        color="#101030"
        wireframe
        emissive="#a78bfa"
        emissiveIntensity={0.4 + progress}
        transparent
        opacity={0.5}
      />
    </mesh>
  );
}
