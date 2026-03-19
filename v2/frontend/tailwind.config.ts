import type { Config } from "tailwindcss";
const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: "#0a0e17", card: "#141b2d", hover: "#1a2332" },
        border: { DEFAULT: "#1e3a5f" },
        accent: { blue: "#1976d2", red: "#c62828", green: "#2e7d32", orange: "#e65100", purple: "#6a1b9a" },
      },
    },
  },
  plugins: [],
};
export default config;
