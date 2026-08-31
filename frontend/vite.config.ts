import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend defaults to http://localhost:8000. Override with VITE_BACKEND.
const backend = process.env.VITE_BACKEND || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // bind 0.0.0.0 so other devices on the LAN can open the app
    port: 5173,
    proxy: {
      "/api": {
        target: backend,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("error", () => {});
        },
      },
      "/data": {
        target: backend,
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on("error", () => {});
        },
      },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
