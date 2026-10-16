import type { Config } from "tailwindcss";

const v = (name: string) => `var(--${name})`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        bg: v("bg"),
        panel: v("panel"),
        line: v("border"),
        ink: v("ink"),
        muted: v("muted"),
        "muted-strong": v("muted-strong"),
        link: v("link"),
        "warn-bg": v("warn-bg"),
        "warn-ink": v("warn-ink"),
        control: v("control"),
        treatment: v("treatment"),
        accent: v("accent"),
        good: v("good"),
        bad: v("bad"),
      },
      fontFamily: { sans: ["var(--font-sans)", "system-ui", "sans-serif"] },
      maxWidth: { prose: "1100px", cards: "1480px" },
    },
  },
  plugins: [],
};

export default config;
