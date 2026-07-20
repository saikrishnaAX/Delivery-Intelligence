import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";
import { backendLauncherPlugin } from "./vite-backend-launcher-plugin";

export default defineConfig({
  plugins: [react(), backendLauncherPlugin()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
    server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8003",
        changeOrigin: true,
        timeout: 300000,
      },
    },
  },
});
