/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#09090B",
        panel: "rgba(24,24,27,0.72)",
        line: "rgba(255,255,255,0.08)",
        text: "#FAFAFA",
        muted: "#A1A1AA",
        up: "#22C55E",
        down: "#EF4444",
        warn: "#EAB308"
      },
      boxShadow: {
        glass: "0 18px 60px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.06)"
      }
    }
  },
  plugins: []
};
