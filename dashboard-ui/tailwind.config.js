/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0a1628",
          900: "#0f1d32",
          800: "#1a2942",
          700: "#243552",
          600: "#3d5278",
          500: "#5a6d8a",
        },
        canvas: {
          50: "#faf8f5",
          100: "#f3efe8",
          200: "#e8e2d8",
          300: "#d9d0c3",
        },
        bahi: {
          50: "#e8f6f3",
          100: "#ccebe4",
          200: "#9dd9cc",
          500: "#148077",
          600: "#0f655e",
          700: "#0b4f49",
          800: "#083d38",
        },
        sidebar: {
          DEFAULT: "#0a1628",
          hover: "#132038",
          active: "#1a2942",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(10,22,40,0.04), 0 4px 16px rgba(10,22,40,0.06)",
        "card-hover": "0 4px 20px rgba(10,22,40,0.08)",
        drawer: "-8px 0 32px rgba(10,22,40,0.12)",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
      },
      animation: {
        shimmer: "shimmer 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
