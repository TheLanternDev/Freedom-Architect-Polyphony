import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /* ── Premium palette (Design System v1) ── */
        app: {
          DEFAULT: "#050505",
          deep: "#030303",
        },
        surface: {
          DEFAULT: "rgba(18, 18, 15, 0.60)",
          raised: "rgba(28, 27, 21, 0.72)",
          overlay: "rgba(34, 32, 25, 0.82)",
        },
        gold: {
          DEFAULT: "#D4AF6A",
          light: "#F4D896",
          dim: "rgba(212, 175, 106, 0.12)",
          muted: "rgba(212, 175, 106, 0.55)",
        },
        teal: {
          DEFAULT: "#3D8B8B",
          light: "#5AA8A8",
          dark: "#2D6B6B",
          dim: "rgba(61, 139, 139, 0.12)",
        },
        text: {
          primary: "#EEF0E6",
          secondary: "#B8B2A4",
          tertiary: "#857F72",
        },
        border: {
          DEFAULT: "rgba(212, 175, 106, 0.20)",
          subtle: "rgba(212, 175, 106, 0.10)",
          focus: "rgba(212, 175, 106, 0.45)",
        },
        /* Legacy aliases — mapped to new palette for gradual migration */
        navy: {
          DEFAULT: "#050505",
          800: "#121210",
          700: "#1c1b15",
        },
      },
      fontFamily: {
        sans: ['"Space Grotesk"', "DM Sans", "system-ui", "-apple-system", "sans-serif"],
        serif: ['"Cormorant Garamond"', '"DM Serif Display"', "Georgia", "Cambria", "serif"],
        display: ['"Cormorant Garamond"', '"DM Serif Display"', "Georgia", "serif"],
      },
      fontSize: {
        "display-lg": ["1.75rem", { lineHeight: "1.25", letterSpacing: "-0.01em" }],
        "display-md": ["1.375rem", { lineHeight: "1.3", letterSpacing: "-0.005em" }],
        "label-sm": ["0.625rem", { lineHeight: "1.4", letterSpacing: "0.14em" }],
        "label-xs": ["0.5625rem", { lineHeight: "1.4", letterSpacing: "0.16em" }],
      },
      letterSpacing: {
        eyebrow: "0.14em",
        "wide-label": "0.08em",
        display: "-0.01em",
      },
      spacing: {
        4.5: "1.125rem",
        5.5: "1.375rem",
        7.5: "1.875rem",
        13: "3.25rem",
        15: "3.75rem",
        18: "4.5rem",
      },
      borderRadius: {
        card: "12px",
        surface: "10px",
        control: "8px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0, 0, 0, 0.24), 0 4px 16px rgba(0, 0, 0, 0.18)",
        elevated:
          "0 2px 4px rgba(0, 0, 0, 0.28), 0 8px 32px rgba(0, 0, 0, 0.22)",
        glowGold: "0 0 24px rgba(212, 175, 106, 0.16)",
        glowTeal: "0 0 20px rgba(61, 139, 139, 0.1)",
        inset: "inset 0 1px 0 rgba(255, 255, 255, 0.04)",
      },
      transitionDuration: {
        premium: "220ms",
      },
      transitionTimingFunction: {
        premium: "cubic-bezier(0.4, 0, 0.2, 1)",
        entrance: "cubic-bezier(0.25, 0.1, 0.25, 1)",
      },
      keyframes: {
        "aw-fade-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "aw-bar-up": {
          from: { opacity: "0", transform: "translateY(100%)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "aw-pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
      },
      animation: {
        "aw-fade-up": "aw-fade-up 0.38s cubic-bezier(0.25, 0.1, 0.25, 1) forwards",
        "aw-bar-up": "aw-bar-up 0.32s cubic-bezier(0.25, 0.1, 0.25, 1) forwards",
        "aw-pulse-soft": "aw-pulse-soft 2.4s ease-in-out infinite",
      },
      backgroundImage: {
        "surface-gradient":
          "linear-gradient(165deg, rgba(255,255,255,0.025) 0%, rgba(255,255,255,0) 48%, rgba(0,0,0,0.08) 100%)",
        "app-gradient":
          "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(212,175,106,0.05) 0%, transparent 55%)",
      },
    },
  },
  plugins: [],
} satisfies Config;
