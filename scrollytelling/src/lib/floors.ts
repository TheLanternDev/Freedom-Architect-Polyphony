export type FloorId =
  | "null"
  | "abyss"
  | "monolith"
  | "bloom"
  | "forge"
  | "grid"
  | "quantum"
  | "mirror"
  | "ascent"
  | "singularity";

export type FloorDef = {
  id: FloorId;
  index: number;
  /** Unique narrative beat — conveyed spatially, not as copy */
  event: string;
  /** Approx scroll height in vh */
  vh: number;
  palette: {
    bg: string;
    fog: string;
    accent: string;
    secondary: string;
    emissive: string;
  };
  fogDensity: number;
  bloom: { intensity: number; threshold: number; smoothing: number };
  dof: { focusDistance: number; focalLength: number; bokehScale: number };
  camera: {
    start: [number, number, number];
    end: [number, number, number];
    lookStart: [number, number, number];
    lookEnd: [number, number, number];
  };
};

/** Phase 0 spine: VERGE — ten strata of becoming. Scroll is the timeline. */
export const FLOORS: FloorDef[] = [
  {
    id: "null",
    index: 0,
    event: "Ignition — a single ember refuses the void",
    vh: 130,
    palette: {
      bg: "#020203",
      fog: "#050508",
      accent: "#ff6b2c",
      secondary: "#1a0a04",
      emissive: "#ff9a4a",
    },
    fogDensity: 0.045,
    bloom: { intensity: 2.4, threshold: 0.2, smoothing: 0.9 },
    dof: { focusDistance: 0.01, focalLength: 0.04, bokehScale: 3.2 },
    camera: {
      start: [0, 0.6, 8],
      end: [0.4, 0.2, 4.2],
      lookStart: [0, 0, 0],
      lookEnd: [0, 0, 0],
    },
  },
  {
    id: "abyss",
    index: 1,
    event: "Submersion — pressure speaks in caustics",
    vh: 140,
    palette: {
      bg: "#001018",
      fog: "#003040",
      accent: "#2ee6ff",
      secondary: "#0a3d55",
      emissive: "#6fffff",
    },
    fogDensity: 0.028,
    bloom: { intensity: 1.6, threshold: 0.35, smoothing: 0.7 },
    dof: { focusDistance: 0.014, focalLength: 0.05, bokehScale: 2.4 },
    camera: {
      start: [0, 4, 10],
      end: [2, -3, 6],
      lookStart: [0, 0, 0],
      lookEnd: [0, -2, -2],
    },
  },
  {
    id: "monolith",
    index: 2,
    event: "Judgment — stone remembers every refusal",
    vh: 135,
    palette: {
      bg: "#0c0b0a",
      fog: "#2a241c",
      accent: "#c4a574",
      secondary: "#4a3f32",
      emissive: "#e8d5a8",
    },
    fogDensity: 0.018,
    bloom: { intensity: 0.5, threshold: 0.7, smoothing: 0.4 },
    dof: { focusDistance: 0.02, focalLength: 0.035, bokehScale: 1.6 },
    camera: {
      start: [-6, 3, 14],
      end: [4, 8, 8],
      lookStart: [0, 2, 0],
      lookEnd: [0, 6, -4],
    },
  },
  {
    id: "bloom",
    index: 3,
    event: "Germination — soft geometry learns to breathe",
    vh: 145,
    palette: {
      bg: "#06140c",
      fog: "#0d2a1a",
      accent: "#7dffb3",
      secondary: "#2d6b4a",
      emissive: "#b8ff6a",
    },
    fogDensity: 0.022,
    bloom: { intensity: 2.8, threshold: 0.15, smoothing: 0.85 },
    dof: { focusDistance: 0.012, focalLength: 0.045, bokehScale: 2.8 },
    camera: {
      start: [0, 1.5, 9],
      end: [3, 2.5, 4],
      lookStart: [0, 1, 0],
      lookEnd: [0, 1.5, -1],
    },
  },
  {
    id: "forge",
    index: 4,
    event: "Temper — heat forces form from noise",
    vh: 130,
    palette: {
      bg: "#140404",
      fog: "#3a1008",
      accent: "#ff3b1f",
      secondary: "#8a2208",
      emissive: "#ffaa33",
    },
    fogDensity: 0.032,
    bloom: { intensity: 3.2, threshold: 0.1, smoothing: 0.95 },
    dof: { focusDistance: 0.016, focalLength: 0.03, bokehScale: 2.2 },
    camera: {
      start: [0, 2, 11],
      end: [-2, 1, 5],
      lookStart: [0, 0, 0],
      lookEnd: [0, 0.5, -2],
    },
  },
  {
    id: "grid",
    index: 5,
    event: "Acceleration — corridors invent urgency",
    vh: 150,
    palette: {
      bg: "#050510",
      fog: "#15153a",
      accent: "#ff2bd6",
      secondary: "#2b6fff",
      emissive: "#00f0ff",
    },
    fogDensity: 0.015,
    bloom: { intensity: 2.2, threshold: 0.25, smoothing: 0.8 },
    dof: { focusDistance: 0.018, focalLength: 0.028, bokehScale: 1.8 },
    camera: {
      start: [0, 1.2, 16],
      end: [0, 3, 2],
      lookStart: [0, 1, -4],
      lookEnd: [0, 2, -20],
    },
  },
  {
    id: "quantum",
    index: 6,
    event: "Superposition — paths that almost were",
    vh: 140,
    palette: {
      bg: "#04040c",
      fog: "#101030",
      accent: "#a78bfa",
      secondary: "#38bdf8",
      emissive: "#f0abfc",
    },
    fogDensity: 0.02,
    bloom: { intensity: 2.0, threshold: 0.3, smoothing: 0.75 },
    dof: { focusDistance: 0.01, focalLength: 0.055, bokehScale: 3.5 },
    camera: {
      start: [5, 3, 10],
      end: [-3, 0, 5],
      lookStart: [0, 0, 0],
      lookEnd: [0, 0, 0],
    },
  },
  {
    id: "mirror",
    index: 7,
    event: "Fracture — the self multiplies to survive",
    vh: 135,
    palette: {
      bg: "#0a0a12",
      fog: "#1c1c2e",
      accent: "#e2e8f0",
      secondary: "#64748b",
      emissive: "#94a3b8",
    },
    fogDensity: 0.012,
    bloom: { intensity: 1.4, threshold: 0.4, smoothing: 0.6 },
    dof: { focusDistance: 0.015, focalLength: 0.04, bokehScale: 2.0 },
    camera: {
      start: [0, 0, 10],
      end: [2, 1, 3],
      lookStart: [0, 0, 0],
      lookEnd: [0, 0, -2],
    },
  },
  {
    id: "ascent",
    index: 8,
    event: "Elevation — horizon becomes scripture",
    vh: 145,
    palette: {
      bg: "#87a0c0",
      fog: "#c8d8ec",
      accent: "#fff6e0",
      secondary: "#6b8fbe",
      emissive: "#ffe8a0",
    },
    fogDensity: 0.008,
    bloom: { intensity: 1.8, threshold: 0.5, smoothing: 0.7 },
    dof: { focusDistance: 0.025, focalLength: 0.02, bokehScale: 1.2 },
    camera: {
      start: [0, 2, 20],
      end: [0, 18, 8],
      lookStart: [0, 4, 0],
      lookEnd: [0, 12, -10],
    },
  },
  {
    id: "singularity",
    index: 9,
    event: "Convergence — all strata wear one face",
    vh: 150,
    palette: {
      bg: "#000000",
      fog: "#1a0510",
      accent: "#ff6b2c",
      secondary: "#2ee6ff",
      emissive: "#ffffff",
    },
    fogDensity: 0.04,
    bloom: { intensity: 4.0, threshold: 0.05, smoothing: 0.98 },
    dof: { focusDistance: 0.008, focalLength: 0.06, bokehScale: 4.0 },
    camera: {
      start: [0, 0, 14],
      end: [0, 0, 1.2],
      lookStart: [0, 0, 0],
      lookEnd: [0, 0, 0],
    },
  },
];

export const TOTAL_VH = FLOORS.reduce((s, f) => s + f.vh, 0);

/** Cumulative [start, end] normalized progress 0..1 for each floor */
export function floorRanges(): { id: FloorId; start: number; end: number }[] {
  let acc = 0;
  return FLOORS.map((f) => {
    const start = acc / TOTAL_VH;
    acc += f.vh;
    const end = acc / TOTAL_VH;
    return { id: f.id, start, end };
  });
}

export function floorLocalProgress(global: number, start: number, end: number) {
  if (end <= start) return 0;
  return Math.min(1, Math.max(0, (global - start) / (end - start)));
}
