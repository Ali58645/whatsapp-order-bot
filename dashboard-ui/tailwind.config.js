/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0c1222",
          900: "#141c2e",
          800: "#1e2a42",
          700: "#2a3a58",
          600: "#3d5278",
        },
        mist: {
          50: "#f0f4f8",
          100: "#e4ebf3",
          200: "#c9d5e4",
        },
        sea: {
          500: "#1a9b8e",
          600: "#148077",
          700: "#0f655e",
          50: "#e8f7f5",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
        display: ['"Fraunces"', "Georgia", "serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(12,18,34,0.04), 0 8px 24px rgba(12,18,34,0.06)",
      },
    },
  },
  plugins: [],
};
