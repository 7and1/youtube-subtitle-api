import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8010",
      "/health": "http://localhost:8010",
      "/metrics": "http://localhost:8010",
      "/docs": "http://localhost:8010",
      "/openapi.json": "http://localhost:8010",
    },
  },
});
