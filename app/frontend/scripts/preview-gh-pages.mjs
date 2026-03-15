/**
 * Local preview server for GitHub Pages build.
 * Serves dist/ at http://localhost:4173/hedge-fund-tracker/
 * with SPA fallback (serves index.html for non-file routes).
 */

import { createServer } from "http";
import { readFileSync, existsSync, statSync } from "fs";
import { join, extname } from "path";
import { resolve } from "path";

const distDir = resolve(import.meta.dirname, "../dist");
const BASE = "/hedge-fund-tracker";
const PORT = 4173;

const MIME_TYPES = {
  ".html": "text/html",
  ".js": "application/javascript",
  ".css": "text/css",
  ".json": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".csv": "text/csv",
};

const server = createServer((req, res) => {
  let url = req.url.split("?")[0];

  // Strip base path
  if (url.startsWith(BASE)) {
    url = url.slice(BASE.length) || "/";
  }

  const filePath = resolve(distDir, "." + url);

  // Prevent path traversal: ensure resolved path stays within distDir
  if (!filePath.startsWith(distDir + "/") && filePath !== distDir) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  // If file exists, serve it
  if (existsSync(filePath) && statSync(filePath).isFile()) {
    const ext = extname(filePath);
    const mime = MIME_TYPES[ext] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": mime });
    res.end(readFileSync(filePath));
    return;
  }

  // SPA fallback: serve index.html
  const indexPath = join(distDir, "index.html");
  if (existsSync(indexPath)) {
    res.writeHead(200, { "Content-Type": "text/html" });
    res.end(readFileSync(indexPath));
    return;
  }

  res.writeHead(404);
  res.end("Not found");
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`\n  GH Pages preview: http://localhost:${PORT}${BASE}/\n`);
});
