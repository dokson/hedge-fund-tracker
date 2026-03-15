/**
 * Copies database CSV files from the repo root database/ directory
 * into app/frontend/dist/database/ for GitHub Pages static deployment.
 *
 * Also generates:
 *  - manifest.json for each quarter (list of fund names)
 *  - metadata.json with build info
 *
 * Run AFTER `vite build` so dist/ already exists.
 */

import {
  cpSync,
  mkdirSync,
  existsSync,
  readdirSync,
  readFileSync,
  writeFileSync,
  statSync,
} from "fs";
import { resolve, join } from "path";

// import.meta.dirname = app/frontend/scripts/
// repo root = app/frontend/scripts/../../..  (up 3 levels: scripts → frontend → app → repo root)
const repoRoot = resolve(import.meta.dirname, "../../..");
const sourceDir = resolve(repoRoot, "database");
const distDir = resolve(import.meta.dirname, "../dist");
const targetDir = resolve(distDir, "database");

if (!existsSync(distDir)) {
  console.error("dist/ directory not found. Run `vite build` first.");
  process.exit(1);
}

if (!existsSync(targetDir)) mkdirSync(targetDir, { recursive: true });

// --- Static CSV files ---
const staticFiles = [
  "hedge_funds.csv",
  "excluded_hedge_funds.csv",
  "stocks.csv",
  "non_quarterly.csv",
  "models.csv",
];

for (const file of staticFiles) {
  const src = resolve(sourceDir, file);
  if (existsSync(src)) {
    cpSync(src, resolve(targetDir, file));
    console.log(`  ${file}`);
  }
}

// --- GICS hierarchy ---
const gicsSrc = resolve(sourceDir, "GICS");
if (existsSync(gicsSrc)) {
  const gicsDest = resolve(targetDir, "GICS");
  mkdirSync(gicsDest, { recursive: true });
  cpSync(resolve(gicsSrc, "hierarchy.csv"), resolve(gicsDest, "hierarchy.csv"));
  console.log(`  GICS/hierarchy.csv`);
}

// --- Quarterly data directories (e.g., 2025Q1, 2025Q2, ...) ---
const quarters = readdirSync(sourceDir).filter((entry) => {
  const fullPath = resolve(sourceDir, entry);
  return statSync(fullPath).isDirectory() && /^\d{4}Q[1-4]$/.test(entry);
});

let latestQuarter = "N/A";
if (quarters.length > 0) {
  quarters.sort(); // chronological order
  latestQuarter = quarters[quarters.length - 1];
}

const quarterManifests = {};

for (const quarter of quarters) {
  const qSrc = resolve(sourceDir, quarter);
  const qDest = resolve(targetDir, quarter);
  mkdirSync(qDest, { recursive: true });

  const csvFiles = readdirSync(qSrc).filter((f) => f.endsWith(".csv"));

  // Copy all CSVs
  for (const csv of csvFiles) {
    cpSync(resolve(qSrc, csv), resolve(qDest, csv));
  }

  // Generate manifest: list of fund names (without .csv extension)
  const fundNames = csvFiles.map((f) => f.replace(".csv", ""));
  writeFileSync(
    resolve(qDest, "manifest.json"),
    JSON.stringify(fundNames, null, 2)
  );

  quarterManifests[quarter] = fundNames.length;
  console.log(`  ${quarter}/ (${fundNames.length} funds)`);
}

// --- Global metadata ---
// Count unique funds from the latest quarter
let fundCount = 0;
if (latestQuarter !== "N/A") {
  const manifestPath = resolve(targetDir, latestQuarter, "manifest.json");
  if (existsSync(manifestPath)) {
    const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
    fundCount = manifest.length;
  }
}

const metadata = {
  latestQuarter,
  buildDate: new Date().toISOString().slice(0, 10),
  fundCount,
  quarters: quarters,
};

writeFileSync(
  resolve(targetDir, "metadata.json"),
  JSON.stringify(metadata, null, 2)
);
console.log(`  metadata.json (${latestQuarter}, ${fundCount} funds)`);

console.log("\nDatabase files copied to dist/database/");
