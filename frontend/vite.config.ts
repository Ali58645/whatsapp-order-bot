import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    base: "/dashboard/",
    build: {
      // Vite builds straight into the backend's static dir, which FastAPI
      // serves at /dashboard. The two projects stay separate otherwise.
      outDir: "../backend/app/static/dashboard",
      emptyOutDir: true,
    },
    server: {
      port: 5173,
      proxy: {
        "/api": apiTarget,
      },
    },
  };
});
