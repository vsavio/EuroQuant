/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0B0E14",      // Bloomberg black-blue
          card: "#151922",    // dark card
          border: "#232936",  // line separator
          accent: "#FF9900",  // Bloomberg orange
          text: "#E2E8F0",    // soft white
          muted: "#64748B",   // slate
          green: "#00E676",   // strong green
          red: "#FF1744",     // strong red
          yellow: "#FFEA00"   // strong yellow
        }
      }
    },
  },
  plugins: [],
}
