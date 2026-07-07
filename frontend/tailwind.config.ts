import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#101A2E",
        line: "#E3E8F1",
        paper: "#F5F7FB",
        pass: "#0B8F5F",
        fail: "#DF3340",
        warn: "#B26205",
        run: "#2B5CE6",
        brand: {
          DEFAULT: "#0E7A6C",
          deep: "#0A5C52",
          soft: "#E8F5F2",
        },
        night: "#0B1322",
      },
      fontFamily: {
        sans: [
          '"Hanken Grotesk Variable"',
          '"Segoe UI"',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Microsoft YaHei"',
          "system-ui",
          "sans-serif",
        ],
        display: [
          '"Hanken Grotesk Variable"',
          '"Segoe UI"',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Microsoft YaHei"',
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono Variable"',
          '"Cascadia Code"',
          "Consolas",
          '"Microsoft YaHei"',
          "monospace",
        ],
      },
      boxShadow: {
        card: "0 1px 2px rgba(16, 26, 46, 0.04), 0 10px 28px -14px rgba(16, 26, 46, 0.12)",
        lift: "0 2px 4px rgba(16, 26, 46, 0.05), 0 22px 44px -16px rgba(16, 26, 46, 0.20)",
        glow: "0 0 0 1px rgba(14, 122, 108, 0.10), 0 14px 44px -10px rgba(43, 92, 230, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
