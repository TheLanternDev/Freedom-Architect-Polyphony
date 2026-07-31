"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { noiseGLSL } from "@/shaders/noise";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorNull() {
  const ember = useRef<THREE.Mesh>(null);
  const ring = useRef<THREE.Mesh>(null);
  const mat = useRef<THREE.ShaderMaterial>(null);
  const local = useExperience((s) =>
    s.activeFloor === "null" ? s.localProgress : s.activeIndex > 0 ? 1 : 0,
  );

  const emberMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        uniforms: {
          uTime: { value: 0 },
          uProgress: { value: 0 },
        },
        vertexShader: /* glsl */ `
          varying vec2 vUv;
          void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }
        `,
        fragmentShader: /* glsl */ `
          uniform float uTime; uniform float uProgress;
          varying vec2 vUv;
          ${noiseGLSL}
          void main(){
            vec2 p = vUv - 0.5;
            float d = length(p);
            float n = fbm(vec3(p * 4.0, uTime * 0.5));
            float core = smoothstep(0.22, 0.0, d - n * 0.05);
            float glow = smoothstep(0.5, 0.0, d) * (0.4 + uProgress);
            vec3 col = mix(vec3(1.0, 0.35, 0.08), vec3(1.0, 0.85, 0.4), core);
            gl_FragColor = vec4(col, (core + glow * 0.6) * (0.3 + uProgress * 1.4));
          }
        `,
      }),
    [],
  );

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    emberMat.uniforms.uTime.value = t;
    emberMat.uniforms.uProgress.value = local;
    if (ember.current) {
      const s = 0.15 + local * 1.4 + Math.sin(t * 2) * 0.03;
      ember.current.scale.setScalar(s);
      ember.current.rotation.z = t * 0.2;
    }
    if (ring.current) {
      ring.current.rotation.x = Math.PI / 2;
      ring.current.rotation.z = t * 0.15;
      const rs = 0.5 + local * 8;
      ring.current.scale.setScalar(rs);
      (ring.current.material as THREE.MeshBasicMaterial).opacity =
        Math.max(0, 0.55 - local * 0.4);
    }
  });

  return (
    <FloorShell id="null">
      {/* ultra background */}
      <mesh position={[0, 0, -20]}>
        <planeGeometry args={[80, 80]} />
        <meshBasicMaterial color="#020203" />
      </mesh>
      {/* mid ambient life */}
      <GPUPoints
        count={6000}
        color="#ff6b2c"
        size={0.035}
        spread={18}
        mode="embers"
        scrollDrive={local}
        speed={0.35}
      />
      <GPUPoints
        count={2000}
        color="#1a3050"
        size={0.02}
        spread={30}
        mode="stars"
        scrollDrive={local}
        speed={0.1}
      />
      {/* foreground ember */}
      <mesh ref={ember}>
        <planeGeometry args={[2, 2]} />
        <primitive object={emberMat} ref={mat} attach="material" />
      </mesh>
      <mesh ref={ring}>
        <torusGeometry args={[1, 0.01, 16, 128]} />
        <meshBasicMaterial color="#ff9a4a" transparent opacity={0.4} />
      </mesh>
      {/* volumetric shards reacting to camera */}
      {Array.from({ length: 12 }).map((_, i) => (
        <mesh
          key={i}
          position={[
            Math.cos((i / 12) * Math.PI * 2) * (2 + local * 4),
            Math.sin(i) * 0.5,
            Math.sin((i / 12) * Math.PI * 2) * (2 + local * 4),
          ]}
          rotation={[i, i * 0.3, 0]}
        >
          <boxGeometry args={[0.02, 0.8 + (i % 3) * 0.4, 0.02]} />
          <meshStandardMaterial
            color="#ff6b2c"
            emissive="#ff6b2c"
            emissiveIntensity={0.8 + local}
            transparent
            opacity={0.35 + local * 0.4}
          />
        </mesh>
      ))}
      <pointLight color="#ff6b2c" intensity={2 + local * 6} distance={20} />
      <ambientLight intensity={0.05} />
    </FloorShell>
  );
}
