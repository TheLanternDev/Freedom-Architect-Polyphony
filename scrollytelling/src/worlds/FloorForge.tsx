"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { noiseGLSL } from "@/shaders/noise";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorForge() {
  const local = useExperience((s) =>
    s.activeFloor === "forge" ? s.localProgress : s.activeIndex > 4 ? 1 : 0,
  );
  const lava = useRef<THREE.Mesh>(null);
  const anvil = useRef<THREE.Mesh>(null);

  const lavaMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uProgress: { value: 0 },
        },
        vertexShader: /* glsl */ `
          uniform float uTime; uniform float uProgress;
          varying vec2 vUv; varying float vH;
          ${noiseGLSL}
          void main(){
            vUv = uv;
            vec3 p = position;
            float n = fbm(vec3(p.xy * 1.5, uTime * 0.3));
            p.z += n * (0.2 + uProgress * 0.5);
            vH = n;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p,1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform float uTime; uniform float uProgress;
          varying vec2 vUv; varying float vH;
          ${noiseGLSL}
          void main(){
            float n = fbm(vec3(vUv * 4.0, uTime * 0.25));
            vec3 cool = vec3(0.15, 0.02, 0.0);
            vec3 hot = vec3(1.0, 0.35, 0.05);
            vec3 core = vec3(1.0, 0.85, 0.3);
            vec3 col = mix(cool, hot, n + vH);
            col = mix(col, core, smoothstep(0.45, 0.8, n + uProgress * 0.3));
            gl_FragColor = vec4(col, 1.0);
          }
        `,
      }),
    [],
  );

  useFrame((state) => {
    lavaMat.uniforms.uTime.value = state.clock.elapsedTime;
    lavaMat.uniforms.uProgress.value = local;
    if (anvil.current) {
      anvil.current.position.y = 0.4 + Math.sin(state.clock.elapsedTime * 2) * 0.02 * local;
      anvil.current.rotation.y = local * Math.PI * 0.5;
    }
  });

  return (
    <FloorShell id="forge">
      <mesh position={[0, 0, -16]}>
        <planeGeometry args={[60, 40]} />
        <meshBasicMaterial color="#140404" />
      </mesh>
      <mesh ref={lava} rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.2, 0]}>
        <planeGeometry args={[24, 24, 96, 96]} />
        <primitive object={lavaMat} attach="material" />
      </mesh>
      <GPUPoints
        count={5000}
        color="#ffaa33"
        size={0.05}
        spread={14}
        mode="sparks"
        scrollDrive={local}
        speed={0.7}
      />
      <mesh ref={anvil} position={[0, 0.5, 0]} castShadow>
        <boxGeometry args={[2.4, 0.8, 1.4]} />
        <meshStandardMaterial
          color="#2a1210"
          metalness={0.85}
          roughness={0.25}
          emissive="#ff3b1f"
          emissiveIntensity={0.15 + local * 0.5}
        />
      </mesh>
      {/* hammer strikes as morphing bars */}
      {Array.from({ length: 6 }).map((_, i) => (
        <mesh
          key={i}
          position={[(i - 2.5) * 1.2, 1.5 + Math.sin(i + local * 8) * 0.8, -1]}
          rotation={[0, 0, Math.sin(local * 10 + i) * 0.4]}
        >
          <boxGeometry args={[0.15, 1.5, 0.15]} />
          <meshStandardMaterial
            color="#8a2208"
            emissive="#ffaa33"
            emissiveIntensity={0.4 + local}
            metalness={0.6}
            roughness={0.3}
          />
        </mesh>
      ))}
      <pointLight color="#ff3b1f" intensity={8 + local * 10} position={[0, 2, 2]} distance={28} />
      <pointLight color="#ffaa33" intensity={4} position={[-3, 1, -2]} distance={18} />
      <ambientLight intensity={0.1} />
    </FloorShell>
  );
}
