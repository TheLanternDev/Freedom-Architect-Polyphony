"use client";

import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { noiseGLSL } from "@/shaders/noise";

type Props = {
  count?: number;
  color?: string;
  size?: number;
  spread?: number;
  speed?: number;
  scrollDrive?: number;
  mode?: "embers" | "dust" | "sparks" | "spores" | "stars" | "quantum";
};

export function GPUPoints({
  count = 4000,
  color = "#ffffff",
  size = 0.04,
  spread = 12,
  speed = 0.4,
  scrollDrive = 0,
  mode = "dust",
}: Props) {
  const ref = useRef<THREE.Points>(null);
  const mat = useRef<THREE.ShaderMaterial>(null);

  const geo = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const pos = new Float32Array(count * 3);
    const a = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      const i3 = i * 3;
      if (mode === "quantum") {
        const r = Math.random() * spread;
        const th = Math.random() * Math.PI * 2;
        const ph = Math.acos(2 * Math.random() - 1);
        pos[i3] = r * Math.sin(ph) * Math.cos(th);
        pos[i3 + 1] = r * Math.sin(ph) * Math.sin(th);
        pos[i3 + 2] = r * Math.cos(ph);
      } else {
        pos[i3] = (Math.random() - 0.5) * spread;
        pos[i3 + 1] = (Math.random() - 0.5) * spread;
        pos[i3 + 2] = (Math.random() - 0.5) * spread;
      }
      a[i] = Math.random();
    }
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("aSeed", new THREE.BufferAttribute(a, 1));
    return g;
  }, [count, spread, mode]);

  const material = useMemo(() => {
    return new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uSize: { value: size },
        uColor: { value: new THREE.Color(color) },
        uScroll: { value: 0 },
        uMode: {
          value:
            mode === "embers"
              ? 0
              : mode === "sparks"
                ? 1
                : mode === "spores"
                  ? 2
                  : mode === "stars"
                    ? 3
                    : mode === "quantum"
                      ? 4
                      : 5,
        },
      },
      vertexShader: /* glsl */ `
        attribute float aSeed;
        uniform float uTime;
        uniform float uSize;
        uniform float uScroll;
        uniform float uMode;
        varying float vAlpha;
        ${noiseGLSL}
        void main(){
          vec3 p = position;
          float t = uTime * (0.2 + aSeed) + uScroll * 4.0;
          if(uMode < 0.5){
            p.y += fract(t * 0.15 + aSeed) * 6.0 - 3.0;
            p.x += snoise(vec3(aSeed*10.0, t, 0.0)) * 0.4;
          } else if(uMode < 1.5){
            p += normalize(p + 0.001) * sin(t + aSeed*6.0) * 0.35;
          } else if(uMode < 2.5){
            p.y += sin(t + aSeed*8.0) * 0.5;
            p.xz += vec2(cos(t*0.3+aSeed), sin(t*0.25+aSeed)) * 0.3;
          } else if(uMode < 3.5){
            p *= 1.0 + 0.02 * sin(t + aSeed);
          } else if(uMode < 4.5){
            float pulse = snoise(p * 0.4 + t * 0.2);
            p += normalize(p + 0.001) * pulse * 0.8;
          } else {
            p.y += snoise(p * 0.2 + t * 0.1) * 0.6;
          }
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = uSize * (300.0 / -mv.z) * (0.6 + aSeed);
          vAlpha = 0.35 + 0.65 * aSeed;
        }
      `,
      fragmentShader: /* glsl */ `
        uniform vec3 uColor;
        varying float vAlpha;
        void main(){
          vec2 uv = gl_PointCoord - 0.5;
          float d = length(uv);
          float alpha = smoothstep(0.5, 0.0, d) * vAlpha;
          gl_FragColor = vec4(uColor, alpha);
        }
      `,
    });
  }, [color, size, mode]);

  useFrame((state) => {
    if (!mat.current) return;
    mat.current.uniforms.uTime.value = state.clock.elapsedTime * speed;
    mat.current.uniforms.uScroll.value = scrollDrive;
  });

  return (
    <points ref={ref} geometry={geo}>
      <primitive object={material} ref={mat} attach="material" />
    </points>
  );
}
