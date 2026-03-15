import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
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
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
}));
