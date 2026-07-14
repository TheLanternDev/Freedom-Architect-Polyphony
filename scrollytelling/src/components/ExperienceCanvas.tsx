"use client";

import { ScrollCamera } from "@/camera/ScrollCamera";
import { ActiveWorlds } from "@/systems/ActiveWorlds";
import { FloorPostFX } from "@/systems/FloorPostFX";
import { useExperience } from "@/store/experienceStore";
import { Canvas } from "@react-three/fiber";
import { AdaptiveDpr, AdaptiveEvents, Preload } from "@react-three/drei";
import { Suspense, useEffect } from "react";
import * as THREE from "three";

function SceneBoot() {
  const setReady = useExperience((s) => s.setReady);
  useEffect(() => {
    setReady(true);
  }, [setReady]);
  return null;
}

export function ExperienceCanvas() {
  return (
    <div className="fixed inset-0 z-0 h-[100dvh] w-screen">
      <Canvas
        dpr={[1, 1.75]}
        gl={{
          antialias: false,
          powerPreference: "high-performance",
          toneMapping: THREE.ACESFilmicToneMapping,
          toneMappingExposure: 1.05,
          outputColorSpace: THREE.SRGBColorSpace,
        }}
        camera={{ fov: 45, near: 0.1, far: 200, position: [0, 0.6, 8] }}
        shadows
      >
        <Suspense fallback={null}>
          <ScrollCamera />
          <ActiveWorlds />
          <FloorPostFX />
          <AdaptiveDpr pixelated />
          <AdaptiveEvents />
          <Preload all />
          <SceneBoot />
        </Suspense>
      </Canvas>
    </div>
  );
}
