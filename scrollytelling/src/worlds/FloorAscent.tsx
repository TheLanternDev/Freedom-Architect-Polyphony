"use client";

import { Cloud, Sky } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { noiseGLSL } from "@/shaders/noise";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorAscent() {
  const local = useExperience((s) =>
    s.activeFloor === "ascent" ? s.localProgress : s.activeIndex > 8 ? 1 : 0,
  );
  const terrain = useRef<THREE.Mesh>(null);
  const temple = useRef<THREE.Group>(null);

  const terrainMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        uniforms: {
          uTime: { value: 0 },
          uProgress: { value: 0 },
          uColorA: { value: new THREE.Color("#6b8fbe") },
          uColorB: { value: new THREE.Color("#e8f0ff") },
        },
        vertexShader: /* glsl */ `
          uniform float uTime; uniform float uProgress;
          varying vec3 vN; varying float vH;
          ${noiseGLSL}
          void main(){
            vec3 p = position;
            float h = fbm(vec3(p.xz * 0.15, 0.0)) * (2.0 + uProgress * 3.0);
            p.y += h;
            vH = h;
            vN = normal;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p,1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform vec3 uColorA; uniform vec3 uColorB; uniform float uProgress;
          varying float vH;
          void main(){
            vec3 col = mix(uColorA, uColorB, smoothstep(-0.5, 3.0, vH));
            col = mix(col, vec3(1.0, 0.96, 0.88), uProgress * 0.35);
            gl_FragColor = vec4(col, 1.0);
          }
        `,
      }),
    [],
  );

  useFrame((state) => {
    terrainMat.uniforms.uTime.value = state.clock.elapsedTime;
    terrainMat.uniforms.uProgress.value = local;
    if (temple.current) {
      temple.current.position.y = 2 + local * 10;
      temple.current.rotation.y = state.clock.elapsedTime * 0.05;
    }
  });

  return (
    <FloorShell id="ascent">
      <Sky
        distance={450000}
        sunPosition={[local * 40 - 10, 8 + local * 20, -30]}
        inclination={0.48}
        azimuth={0.25}
        mieCoefficient={0.004}
        mieDirectionalG={0.8}
        rayleigh={local * 2 + 0.5}
        turbidity={4}
      />
      <Cloud
        opacity={0.45}
        speed={0.2}
        segments={20}
        bounds={[12, 3, 12]}
        position={[0, 10 + local * 6, -8]}
        color="#fff6e0"
      />
      <mesh ref={terrain} rotation={[-Math.PI / 2, 0, 0]} position={[0, -2, 0]}>
        <planeGeometry args={[60, 60, 96, 96]} />
        <primitive object={terrainMat} attach="material" />
      </mesh>
      <group ref={temple}>
        <mesh position={[0, 1, 0]}>
          <cylinderGeometry args={[1.2, 1.6, 0.4, 6]} />
          <meshStandardMaterial color="#e8f0ff" metalness={0.3} roughness={0.4} />
        </mesh>
        {Array.from({ length: 6 }).map((_, i) => {
          const a = (i / 6) * Math.PI * 2;
          return (
            <mesh key={i} position={[Math.cos(a) * 1.1, 2.2, Math.sin(a) * 1.1]}>
              <cylinderGeometry args={[0.12, 0.12, 3.5, 8]} />
              <meshStandardMaterial
                color="#fff6e0"
                emissive="#ffe8a0"
                emissiveIntensity={0.3 + local}
              />
            </mesh>
          );
        })}
        <mesh position={[0, 4.2, 0]}>
          <coneGeometry args={[1.5, 1.2, 6]} />
          <meshStandardMaterial color="#c8d8ec" metalness={0.2} roughness={0.5} />
        </mesh>
      </group>
      {/* god-ray cones */}
      {Array.from({ length: 4 }).map((_, i) => (
        <mesh
          key={i}
          position={[(i - 1.5) * 3, 8, -4]}
          rotation={[0.4, 0, 0.05 * i]}
        >
          <coneGeometry args={[2, 18, 16, 1, true]} />
          <meshBasicMaterial
            color="#ffe8a0"
            transparent
            opacity={0.04 + local * 0.06}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      ))}
      <GPUPoints
        count={2500}
        color="#fff6e0"
        size={0.04}
        spread={30}
        mode="stars"
        scrollDrive={local}
        speed={0.12}
      />
      <directionalLight intensity={1.5 + local} position={[10, 20, 5]} color="#fff6e0" castShadow />
      <ambientLight intensity={0.55} />
      <hemisphereLight args={["#c8d8ec", "#6b8fbe", 0.6]} />
    </FloorShell>
  );
}
