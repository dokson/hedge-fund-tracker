import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ mode }) => ({
  base: mode === "gh-pages" ? "/hedge-fund-tracker/" : "/",
  define: {
    __GH_PAGES_MODE__: mode === "gh-pages",
  },
  server: {
    host: "::",
    port: 8080,
    hmr: { overlay: false },
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
          if (
            id.includes("react-router") ||
            id.includes("/react-dom/") ||
            id.includes("/react/")
          ) {
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
  },
}));
