import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        accent: "#0d9488",
        muted: "#64748b",
        navy: "#1e293b",
        cream: "#fafaf9",
      },
      fontFamily: {
        sans: ["var(--font-dm-sans)", "system-ui", "sans-serif"],
        serif: ["var(--font-source-serif)", "Georgia", "serif"],
      },
      boxShadow: {
        soft: "0 2px 8px rgba(30, 41, 59, 0.06)",
        "soft-lg": "0 4px 16px rgba(30, 41, 59, 0.08)",
        "focus-ring": "0 0 0 3px rgba(13, 148, 136, 0.2)",
      },
      transitionDuration: {
        300: "300ms",
      },
    },
  },
  plugins: [],
};

export default config;
