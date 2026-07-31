"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { GPUPoints } from "@/particles/GPUPoints";
import { noiseGLSL } from "@/shaders/noise";
import { useExperience } from "@/store/experienceStore";
import { FloorShell } from "@/worlds/FloorShell";

export function FloorAbyss() {
  const water = useRef<THREE.Mesh>(null);
  const local = useExperience((s) =>
    s.activeFloor === "abyss" ? s.localProgress : s.activeIndex > 1 ? 1 : 0,
  );

  const waterMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        side: THREE.DoubleSide,
        uniforms: {
          uTime: { value: 0 },
          uProgress: { value: 0 },
          uColorA: { value: new THREE.Color("#003040") },
          uColorB: { value: new THREE.Color("#2ee6ff") },
        },
        vertexShader: /* glsl */ `
          uniform float uTime; uniform float uProgress;
          varying vec3 vPos; varying vec2 vUv;
          ${noiseGLSL}
          void main(){
            vUv = uv;
            vec3 p = position;
            float w = snoise(vec3(p.x*0.3, p.z*0.3, uTime*0.4)) * (0.15 + uProgress*0.35);
            p.y += w;
            vPos = p;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(p,1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform float uTime; uniform float uProgress;
          uniform vec3 uColorA; uniform vec3 uColorB;
          varying vec3 vPos; varying vec2 vUv;
          ${noiseGLSL}
          void main(){
            float c = fbm(vec3(vPos.xz * 0.4, uTime * 0.2));
            float caustic = pow(max(0.0, snoise(vec3(vUv*8.0, uTime*0.5))), 3.0);
            vec3 col = mix(uColorA, uColorB, c * 0.5 + 0.25);
            col += vec3(0.4, 0.9, 1.0) * caustic * (0.5 + uProgress);
            float alpha = 0.55 + 0.25 * uProgress;
            gl_FragColor = vec4(col, alpha);
          }
        `,
      }),
    [],
  );

  useFrame((state) => {
    waterMat.uniforms.uTime.value = state.clock.elapsedTime;
    waterMat.uniforms.uProgress.value = local;
    if (water.current) {
      water.current.position.y = -1.5 - local * 3;
      water.current.rotation.x = -Math.PI / 2;
    }
  });

  return (
    <FloorShell id="abyss">
      <mesh position={[0, 8, -30]}>
        <sphereGeometry args={[40, 32, 32]} />
        <meshBasicMaterial color="#001018" side={THREE.BackSide} />
      </mesh>
      <GPUPoints
        count={5000}
        color="#6fffff"
        size={0.05}
        spread={22}
        mode="dust"
        scrollDrive={local}
        speed={0.25}
      />
      <mesh ref={water} position={[0, -1.5, 0]}>
        <planeGeometry args={[40, 40, 128, 128]} />
        <primitive object={waterMat} attach="material" />
      </mesh>
      {/* kelp-like ribbons */}
      {Array.from({ length: 18 }).map((_, i) => (
        <Kelp key={i} index={i} progress={local} />
      ))}
      {/* light shafts */}
      {Array.from({ length: 5 }).map((_, i) => (
        <mesh
          key={`shaft-${i}`}
          position={[(i - 2) * 2.5, 2, -2 - i]}
          rotation={[0.2, 0, 0.05 * i]}
        >
          <cylinderGeometry args={[0.05, 1.2, 14, 8, 1, true]} />
          <meshBasicMaterial
            color="#6fffff"
            transparent
            opacity={0.06 + local * 0.08}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
      ))}
      <pointLight color="#2ee6ff" intensity={4 + local * 4} position={[0, 4, 2]} distance={30} />
      <pointLight color="#004466" intensity={2} position={[-4, -2, -4]} distance={20} />
      <ambientLight intensity={0.15} />
    </FloorShell>
  );
}

function Kelp({ index, progress }: { index: number; progress: number }) {
  const ref = useRef<THREE.Mesh>(null);
  useFrame((state) => {
    if (!ref.current) return;
    const t = state.clock.elapsedTime;
    ref.current.rotation.z = Math.sin(t * 0.8 + index) * 0.25;
    ref.current.position.y = -2 + Math.sin(t + index) * 0.2 + progress * 0.5;
  });
  const x = ((index % 6) - 2.5) * 1.8;
  const z = (Math.floor(index / 6) - 1) * 2.5 - 2;
  return (
    <mesh ref={ref} position={[x, -2, z]}>
      <capsuleGeometry args={[0.06, 2.2 + (index % 4) * 0.4, 4, 8]} />
      <meshStandardMaterial
        color="#0a5a55"
        emissive="#2ee6ff"
        emissiveIntensity={0.2 + progress * 0.4}
        roughness={0.35}
      />
    </mesh>
  );
}
