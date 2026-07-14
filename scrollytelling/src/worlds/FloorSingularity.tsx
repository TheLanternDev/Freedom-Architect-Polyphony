"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { noiseGLSL } from "@/shaders/noise";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorSingularity() {
  const local = useExperience((s) =>
    s.activeFloor === "singularity" ? s.localProgress : 0,
  );
  const core = useRef<THREE.Mesh>(null);
  const rings = useRef<THREE.Group>(null);

  const coreMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        uniforms: {
          uTime: { value: 0 },
          uProgress: { value: 0 },
        },
        vertexShader: /* glsl */ `
          varying vec3 vN; varying vec3 vP;
          void main(){
            vN = normalize(normalMatrix * normal);
            vP = position;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform float uTime; uniform float uProgress;
          varying vec3 vN; varying vec3 vP;
          ${noiseGLSL}
          void main(){
            float n = fbm(vP * 1.5 + uTime * 0.3);
            float fres = pow(1.0 - abs(dot(normalize(vN), vec3(0.0,0.0,1.0))), 2.0);
            vec3 a = vec3(1.0, 0.42, 0.17);
            vec3 b = vec3(0.18, 0.9, 1.0);
            vec3 c = vec3(1.0);
            vec3 col = mix(a, b, n * 0.5 + 0.5);
            col = mix(col, c, fres * uProgress);
            float alpha = 0.7 + fres * 0.3;
            gl_FragColor = vec4(col * (1.5 + uProgress * 3.0), alpha);
          }
        `,
      }),
    [],
  );

  useFrame((state) => {
    coreMat.uniforms.uTime.value = state.clock.elapsedTime;
    coreMat.uniforms.uProgress.value = local;
    if (core.current) {
      const s = 0.4 + local * 2.8 + Math.sin(state.clock.elapsedTime * 3) * 0.05;
      core.current.scale.setScalar(s);
      core.current.rotation.y = state.clock.elapsedTime * 0.4;
      core.current.rotation.z = state.clock.elapsedTime * 0.2;
    }
    if (rings.current) {
      rings.current.rotation.x = state.clock.elapsedTime * 0.3;
      rings.current.rotation.y = -state.clock.elapsedTime * 0.25;
      rings.current.scale.setScalar(0.5 + local * 3);
    }
  });

  return (
    <FloorShell id="singularity">
      <mesh>
        <sphereGeometry args={[40, 16, 16]} />
        <meshBasicMaterial color="#000000" side={THREE.BackSide} />
      </mesh>
      <GPUPoints
        count={8000}
        color="#ff6b2c"
        size={0.03}
        spread={12}
        mode="quantum"
        scrollDrive={local}
        speed={0.8}
      />
      <GPUPoints
        count={4000}
        color="#2ee6ff"
        size={0.025}
        spread={16}
        mode="embers"
        scrollDrive={local}
        speed={0.5}
      />
      <mesh ref={core}>
        <icosahedronGeometry args={[1, 3]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
      <group ref={rings}>
        {[1.4, 2.1, 2.9, 3.8].map((r, i) => (
          <mesh key={r} rotation={[Math.PI / 2 + i * 0.3, i * 0.5, 0]}>
            <torusGeometry args={[r, 0.015, 12, 128]} />
            <meshBasicMaterial
              color={i % 2 ? "#ff6b2c" : "#2ee6ff"}
              transparent
              opacity={0.5 + local * 0.4}
            />
          </mesh>
        ))}
      </group>
      {/* compressed memory fragments from prior floors */}
      {["#ff6b2c", "#2ee6ff", "#c4a574", "#7dffb3", "#ff3b1f", "#ff2bd6", "#a78bfa", "#e2e8f0"].map(
        (c, i) => (
          <mesh
            key={c}
            position={[
              Math.cos((i / 8) * Math.PI * 2) * (4 - local * 3),
              Math.sin(i) * (2 - local),
              Math.sin((i / 8) * Math.PI * 2) * (4 - local * 3),
            ]}
          >
            <octahedronGeometry args={[0.2, 0]} />
            <meshStandardMaterial color={c} emissive={c} emissiveIntensity={1 + local * 2} toneMapped={false} />
          </mesh>
        ),
      )}
      <pointLight color="#ffffff" intensity={3 + local * 12} distance={40} />
      <pointLight color="#ff6b2c" intensity={6} position={[2, 1, 2]} distance={20} />
      <pointLight color="#2ee6ff" intensity={6} position={[-2, -1, 2]} distance={20} />
      <ambientLight intensity={0.05 + local * 0.2} />
    </FloorShell>
  );
}
