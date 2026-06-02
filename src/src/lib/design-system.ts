/**
 * Architekt Wolności — Design System tokens (v1)
 * Source of truth for programmatic styling outside Tailwind classes.
 */
export const colors = {
  app: "#0A0D14",
  surface: "#11151F",
  surfaceRaised: "#161B28",
  gold: "#C5A46E",
  goldLight: "#D4B888",
  teal: "#3D8B8B",
  tealLight: "#5AA8A8",
  textPrimary: "#E8EBF0",
  textSecondary: "#A6B0C3",
  textTertiary: "#667085",
  border: "#1E2433",
} as const;

export const spacing = {
  grid: 8,
  cardPadding: 24,
  sectionGap: 32,
  pagePadding: 24,
} as const;

export const radius = {
  card: 12,
  surface: 10,
  control: 8,
} as const;

export const typography = {
  fontSans: 'Inter, system-ui, -apple-system, sans-serif',
  fontDisplay: '"DM Serif Display", Georgia, serif',
} as const;

export const motion = {
  duration: "220ms",
  easing: "cubic-bezier(0.4, 0, 0.2, 1)",
} as const;
