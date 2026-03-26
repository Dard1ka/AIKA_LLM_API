/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        neonPink: "#ff4ecd",
        neonCyan: "#22d3ee",
        neonPurple: "#a855f7",
      },
      boxShadow: {
        glow: "0 0 25px rgba(168,85,247,0.6)",
        glowCyan: "0 0 25px rgba(34,211,238,0.6)",
      },
    },
  },
  plugins: [],
}
