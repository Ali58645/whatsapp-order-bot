/** @type {import('tailwindcss').Config} */
function withOpacity(variable) {
  return ({ opacityValue }) =>
    opacityValue === undefined
      ? `hsl(var(${variable}))`
      : `hsl(var(${variable}) / ${opacityValue})`;
}

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        border: withOpacity("--border"),
        input: withOpacity("--input"),
        ring: withOpacity("--ring"),
        background: withOpacity("--background"),
        foreground: withOpacity("--foreground"),
        muted: {
          DEFAULT: withOpacity("--muted"),
          foreground: withOpacity("--muted-foreground"),
        },
        card: {
          DEFAULT: withOpacity("--card"),
          foreground: withOpacity("--card-foreground"),
        },
        popover: {
          DEFAULT: withOpacity("--popover"),
          foreground: withOpacity("--popover-foreground"),
        },
        primary: {
          DEFAULT: withOpacity("--primary"),
          foreground: withOpacity("--primary-foreground"),
        },
        secondary: {
          DEFAULT: withOpacity("--secondary"),
          foreground: withOpacity("--secondary-foreground"),
        },
        accent: {
          DEFAULT: withOpacity("--accent"),
          foreground: withOpacity("--accent-foreground"),
        },
        destructive: {
          DEFAULT: withOpacity("--destructive"),
          foreground: withOpacity("--destructive-foreground"),
        },
        success: {
          DEFAULT: withOpacity("--success"),
          foreground: withOpacity("--success-foreground"),
        },
        warning: {
          DEFAULT: withOpacity("--warning"),
          foreground: withOpacity("--warning-foreground"),
        },
        sidebar: {
          DEFAULT: withOpacity("--sidebar"),
          foreground: withOpacity("--sidebar-foreground"),
          border: withOpacity("--sidebar-border"),
          accent: withOpacity("--sidebar-accent"),
        },
        bahi: {
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', "system-ui", "sans-serif"],
      },
      fontSize: {
        stat: ["2.5rem", { lineHeight: "1", letterSpacing: "-0.04em", fontWeight: "700" }],
        "stat-lg": ["2.75rem", { lineHeight: "1", letterSpacing: "-0.045em", fontWeight: "700" }],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        glow: "0 0 40px -8px hsl(var(--primary) / 0.35)",
        "glow-sm": "0 0 24px -6px hsl(var(--primary) / 0.25)",
        elevated: "0 8px 32px -8px rgba(0,0,0,0.45)",
        drawer: "-12px 0 48px rgba(0,0,0,0.5)",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-200% 0" },
        },
        "pulse-dot": {
          "0%, 100%": { opacity: "1", transform: "scale(1)" },
          "50%": { opacity: "0.55", transform: "scale(0.85)" },
        },
        mesh: {
          "0%, 100%": { transform: "translate(0,0) scale(1)" },
          "33%": { transform: "translate(2%, -3%) scale(1.05)" },
          "66%": { transform: "translate(-2%, 2%) scale(0.97)" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s ease-in-out infinite",
        "pulse-dot": "pulse-dot 2s ease-in-out infinite",
        mesh: "mesh 18s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
