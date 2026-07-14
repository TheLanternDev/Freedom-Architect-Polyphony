"use client";

import dynamic from "next/dynamic";
import type { ComponentType } from "react";
import type { FloorId } from "@/lib/floors";

const FloorNull = dynamic(() => import("@/worlds/FloorNull").then((m) => m.FloorNull), { ssr: false });
const FloorAbyss = dynamic(() => import("@/worlds/FloorAbyss").then((m) => m.FloorAbyss), { ssr: false });
const FloorMonolith = dynamic(() => import("@/worlds/FloorMonolith").then((m) => m.FloorMonolith), { ssr: false });
const FloorBloom = dynamic(() => import("@/worlds/FloorBloom").then((m) => m.FloorBloom), { ssr: false });
const FloorForge = dynamic(() => import("@/worlds/FloorForge").then((m) => m.FloorForge), { ssr: false });
const FloorGrid = dynamic(() => import("@/worlds/FloorGrid").then((m) => m.FloorGrid), { ssr: false });
const FloorQuantum = dynamic(() => import("@/worlds/FloorQuantum").then((m) => m.FloorQuantum), { ssr: false });
const FloorMirror = dynamic(() => import("@/worlds/FloorMirror").then((m) => m.FloorMirror), { ssr: false });
const FloorAscent = dynamic(() => import("@/worlds/FloorAscent").then((m) => m.FloorAscent), { ssr: false });
const FloorSingularity = dynamic(() => import("@/worlds/FloorSingularity").then((m) => m.FloorSingularity), {
  ssr: false,
});

export const WORLD_REGISTRY: Record<FloorId, ComponentType> = {
  null: FloorNull,
  abyss: FloorAbyss,
  monolith: FloorMonolith,
  bloom: FloorBloom,
  forge: FloorForge,
  grid: FloorGrid,
  quantum: FloorQuantum,
  mirror: FloorMirror,
  ascent: FloorAscent,
  singularity: FloorSingularity,
};
