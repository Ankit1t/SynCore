import type { Config } from "tailwindcss";

// Semantic tokens are driven by CSS variables (see globals.css) so the whole UI
// switches between light and dark by toggling the `dark` class on <html>.
// Colors use the `rgb(var(--x) / <alpha-value>)` form so Tailwind opacity
// modifiers (e.g. bg-accent/15) keep working.
const token = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: token("bg"),
        surface: token("surface"),
        elevated: token("elevated"),
        line: token("line"),
        primary: token("primary"),
        muted: token("muted"),
        accent: token("accent"),
        good: token("good"),
        warn: token("warn"),
        bad: token("bad"),
        // legacy aliases so pre-existing pages keep compiling
        panel: token("surface"),
        panel2: token("elevated"),
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl: "0.875rem",
        "2xl": "1.125rem",
      },
      boxShadow: {
        soft: "0 1px 3px 0 rgb(0 0 0 / 0.06), 0 8px 24px -8px rgb(0 0 0 / 0.10)",
        glow: "0 0 0 1px rgb(var(--accent) / 0.35), 0 8px 30px -6px rgb(var(--accent) / 0.35)",
      },
      keyframes: {
        shimmer: {
          "100%": { transform: "translateX(100%)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s infinite",
      },
    },
  },
  plugins: [],
};

export default config;
