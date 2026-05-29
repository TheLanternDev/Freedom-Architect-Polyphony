import { defineConfig, Plugin } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function swVersionPlugin(): Plugin {
  return {
    name: "sw-version-stamp",
    writeBundle() {
      const swPath = path.resolve(__dirname, "dist/sw.js");
      if (fs.existsSync(swPath)) {
        const content = fs.readFileSync(swPath, "utf-8");
        fs.writeFileSync(
          swPath,
          content.replace("__BUILD_TIMESTAMP__", Date.now().toString()),
        );
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), swVersionPlugin()],
  clearScreen: false,
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 1420,
    strictPort: true,
    proxy: {
      "/debate": "http://127.0.0.1:8000",
      "/dreams": "http://127.0.0.1:8000",
      "/generate": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
      "/history": "http://127.0.0.1:8000",
      "/v2": "http://127.0.0.1:8000",
      "/projects": "http://127.0.0.1:8000",
      "/commitment": "http://127.0.0.1:8000",
      "/commitments": "http://127.0.0.1:8000",
      "/admin": "http://127.0.0.1:8000",
      "/personal": "http://127.0.0.1:8000",
      "/cache": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/integrations": "http://127.0.0.1:8000",
      "/voice": "http://127.0.0.1:8000",
      "/edition": "http://127.0.0.1:8000",
      "/demo": "http://127.0.0.1:8000",
      "/costs": "http://127.0.0.1:8000",
    },
  },
  envPrefix: ["VITE_", "TAURI_"],
  build: {
    target: "chrome105",
    minify: !process.env.TAURI_DEBUG ? "esbuild" : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
});
