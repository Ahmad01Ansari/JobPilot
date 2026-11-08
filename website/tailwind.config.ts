import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        obsidian: {
          DEFAULT: "#0F1117",
          deep: "#0B0D12",
          surface: "#161B26",
          border: "#232B3E",
        },
        slate: {
          surface: "#1E293B",
          card: "#182234",
          border: "#334155",
          muted: "#94A3B8",
        },
        orange: {
          safety: "#FF5F15",
          hover: "#E04F0B",
          glow: "rgba(255, 95, 21, 0.25)",
        },
        cyan: {
          pilot: "#0EA5E9",
          glow: "rgba(14, 165, 233, 0.25)",
        },
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "Inter", "-apple-system", "sans-serif"],
        mono: ["var(--font-geist-mono)", "JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;

