// Build-time constant injected by Vite via `define`
// true when built with `--mode gh-pages`, false otherwise
declare const __GH_PAGES_MODE__: boolean;

export const IS_GH_PAGES_MODE =
  typeof __GH_PAGES_MODE__ !== 'undefined' ? __GH_PAGES_MODE__ : false;

// Base path for GitHub Pages subdirectory hosting
export const BASE_PATH = IS_GH_PAGES_MODE ? '/hedge-fund-tracker' : '';

// API base URL: null in GH Pages mode (no backend available), origin-relative in local mode
export const API_BASE = IS_GH_PAGES_MODE ? null : window.location.origin;

// Database base URL for CSV file access
export const DATABASE_URL = IS_GH_PAGES_MODE
  ? '' // relative paths (files served from public/database/)
  : `${window.location.origin}/database`;
