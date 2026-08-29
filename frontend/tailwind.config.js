/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        cmd: {
          bg: "#0a0e14",
          panel: "#111722",
          panel2: "#161d2b",
          border: "#1f2a3a",
          muted: "#6b7a90",
          text: "#c7d3e2",
          accent: "#22d3ee",
          accent2: "#38bdf8",
          ok: "#22c55e",
          warn: "#f59e0b",
          crit: "#ef4444",
          gold: "#fbbf24",
        },
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(34,211,238,0.15), 0 0 24px rgba(34,211,238,0.08)",
      },
    },
  },
  plugins: [],
};
