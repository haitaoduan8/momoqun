import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Neon Aurora 主题色
        bg: {
          DEFAULT: "#000000",
          surface: "#050508",
          card: "#0A0A0F",
          elevated: "#0F0F15",
          hover: "#14141C",
          input: "#08080C",
        },
        accent: {
          DEFAULT: "#00FFC8",
          hover: "#33FFD4",
          dim: "rgba(0,255,200,0.08)",
          glow: "rgba(0,255,200,0.20)",
        },
        electric: {
          DEFAULT: "#0080FF",
          dim: "rgba(0,128,255,0.08)",
        },
        neon: {
          green: "#00FF88",
          yellow: "#FFB800",
          red: "#FF3355",
        },
      },
      borderRadius: {
        xl: "20px",
        lg: "12px",
        md: "10px",
        sm: "8px",
      },
      animation: {
        spotlight: "spotlight 2s ease .75s 1 forwards",
        glow: "glow 2s ease-in-out infinite alternate",
        "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      keyframes: {
        spotlight: {
          "0%": {
            opacity: "0",
            transform: "translate(-72%, -62%) scale(0.5)",
          },
          "100%": {
            opacity: "1",
            transform: "translate(-50%, -40%) scale(1)",
          },
        },
        glow: {
          "0%": {
            boxShadow: "0 0 20px rgba(0,255,200,0.1)",
          },
          "100%": {
            boxShadow: "0 0 40px rgba(0,255,200,0.2)",
          },
        },
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
