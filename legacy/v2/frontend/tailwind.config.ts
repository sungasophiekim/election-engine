import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#060a11", card: "#0c1220", hover: "#111a2e", elevated: "#152238" },
        border: { DEFAULT: "#1a2d4a", bright: "#264166", dim: "#0f1d33" },
        accent: { blue: "#1976d2", red: "#c62828", green: "#2e7d32", orange: "#e65100", purple: "#6a1b9a", cyan: "#0097a7" },
        navy: { 900: "#060a11", 800: "#0c1220", 700: "#111a2e", 600: "#152238", 500: "#1a2d4a" },
        signal: { red: "#ef4444", green: "#22c55e", orange: "#f59e0b", blue: "#3b82f6" },
      },
      fontSize: {
        "metric-xl": ["3.5rem", { lineHeight: "1", fontWeight: "800" }],
        "metric-lg": ["2.25rem", { lineHeight: "1", fontWeight: "700" }],
        "metric-md": ["1.5rem", { lineHeight: "1.1", fontWeight: "700" }],
      },
    },
  },
  plugins: [],
};
export default config;
