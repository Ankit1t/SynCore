import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b1020",
        panel: "#131a2e",
        panel2: "#1b2540",
        line: "#26304d",
        muted: "#8a97b8",
        accent: "#5b8cff",
        good: "#37d39b",
        warn: "#ffb020",
        bad: "#ff5d5d",
      },
    },
  },
  plugins: [],
};

export default config;
