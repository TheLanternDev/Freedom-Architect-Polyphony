# VERGE — Design Singularity Record

## Phase 0 — Concept

**Title:** VERGE  
**Thesis:** Scroll is not navigation — it is the axis of time through ten ontological strata.  
**Story told by:** space, light, particles, shaders, camera, physics — minimal HUD copy only.  
**Spine:** Ignition → Submersion → Judgment → Germination → Temper → Acceleration → Superposition → Fracture → Elevation → Convergence.

## Phase 1 — Visual systems

Each floor owns an exclusive palette, fog density, bloom/DOF profile, and camera rail (see `src/lib/floors.ts`). No two floors share silhouette language (void ember / liquid caustics / instanced stone / transmission flora / lava noise / neon city / entanglement / mirror shards / sky temple / chromatic singularity).

## Phase 2 — Architecture

Modular production tree: `worlds/`, `shaders/`, `particles/`, `camera/`, `scroll/`, `systems/`, `physics/`, `materials/`, `hooks/`. Active ±1 LOD. Dynamic imports. Client Canvas only. Post FX stack swaps with floor.

## Phase 3 — Craft

Kinetic camera damping, GPU point shaders, instancing, Rapier debris, transmission/reflector materials, procedural terrain & water, EffectComposer (Bloom, DOF, SMAA, Vignette, Noise). Performance via AdaptiveDpr, frustum-adjacent activation, code splitting.
