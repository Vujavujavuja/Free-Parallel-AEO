/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#171411",
        panel: "#1f1b18",
        elev: "#28221d",
        edge: "#322c27",
        rule: "#4a4038",
        cream: "#ece7df",
        muted: "#968c82",
        dim: "#776455",
        ember: { DEFAULT: "#ee5e13", 400: "#f3823f", 600: "#e84e07", 700: "#c3420a" },
        wine: { DEFAULT: "#b23656", 500: "#c65674", 700: "#8f2334" },
      },
      fontFamily: {
        display: ['"Cormorant Garamond"', "Georgia", "serif"],
        body: ['"Literata"', "Georgia", "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};
