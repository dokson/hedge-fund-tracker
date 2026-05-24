import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { readFileSync } from "fs";

// Single source-of-truth for the app version: app/frontend/package.json. The
// backend reads the same field at request time (see app/utils/version.py) so
// every surface (sidebar footer, server /health, GH release tag) agrees.
const pkg = JSON.parse(readFileSync(path.resolve(__dirname, "package.json"), "utf-8"));
const APP_VERSION: string = pkg.version;

export default defineConfig(({ mode }) => ({
  base: mode === "gh-pages" ? "/hedge-fund-tracker/" : "/",
  define: {
    __GH_PAGES_MODE__: mode === "gh-pages",
    __APP_VERSION__: JSON.stringify(APP_VERSION),
  },
  server: {
    host: "::",
    port: 8080,
    hmr: { overlay: false },
    // Proxy backend routes to the FastAPI process. Run `pipenv run app` on 8000
    // and `npm run dev` here — edits in src/ hot-reload instantly while the
    // backend (CSV serving, /api/*, SSE) stays untouched.
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
      "/database": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  publicDir: "public",
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return;
          if (id.includes("recharts") || id.includes("d3-")) return "charts";
          if (id.includes("@tanstack")) return "query";
          if (id.includes("react-router") || id.includes("/react-dom/") || id.includes("/react/")) {
            return "react-vendor";
          }
          if (id.includes("@radix-ui")) return "radix";
          return "vendor";
        },
      },
    },
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
}));
