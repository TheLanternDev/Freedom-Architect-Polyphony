"use client";

import { FLOORS } from "@/lib/floors";
import { useExperience } from "@/store/experienceStore";
import {
  Bloom,
  DepthOfField,
  EffectComposer,
  Noise,
  SMAA,
  Vignette,
} from "@react-three/postprocessing";
import { BlendFunction } from "postprocessing";

export function FloorPostFX() {
  const index = useExperience((s) => s.activeIndex);
  const local = useExperience((s) => s.localProgress);
  const reduced = useExperience((s) => s.reducedMotion);
  const floor = FLOORS[index] ?? FLOORS[0];

  const bloomIntensity = floor.bloom.intensity * (0.75 + local * 0.5);
  const bokeh = floor.dof.bokehScale * (reduced ? 0.35 : 1);

  return (
    <EffectComposer multisampling={0} enableNormalPass={false}>
      <DepthOfField
        focusDistance={floor.dof.focusDistance}
        focalLength={floor.dof.focalLength}
        bokehScale={bokeh}
        height={480}
      />
      <Bloom
        intensity={bloomIntensity}
        luminanceThreshold={floor.bloom.threshold}
        luminanceSmoothing={floor.bloom.smoothing}
        mipmapBlur
      />
      <Noise opacity={0.025 + local * 0.02} blendFunction={BlendFunction.SOFT_LIGHT} />
      <Vignette eskil={false} offset={0.15} darkness={0.55 + local * 0.2} />
      <SMAA />
    </EffectComposer>
  );
}
