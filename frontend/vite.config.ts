import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: {
      "/api": {
        target: process.env.REBUILD_API_TARGET ?? "http://127.0.0.1:8002",
        changeOrigin: true,
      },
    },
  },
});

