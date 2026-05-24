// Build-time constants injected by Vite via `define` (see vite.config.ts).
declare const __GH_PAGES_MODE__: boolean;
declare const __APP_VERSION__: string;

export const IS_GH_PAGES_MODE =
  typeof __GH_PAGES_MODE__ !== "undefined" ? __GH_PAGES_MODE__ : false;

/** App version, sourced from app/frontend/package.json at build time. */
export const APP_VERSION = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "0.0.0";

// Base path for GitHub Pages subdirectory hosting
export const BASE_PATH = IS_GH_PAGES_MODE ? "/hedge-fund-tracker" : "";

// API base URL: null in GH Pages mode (no backend available), origin-relative in local mode
export const API_BASE = IS_GH_PAGES_MODE ? null : window.location.origin;

// Database base URL for CSV file access
export const DATABASE_URL = IS_GH_PAGES_MODE
  ? "" // relative paths (files served from public/database/)
  : `${window.location.origin}/database`;

// Cloudinary cloud name used to proxy + cache company logos sourced from FMP.
// The cloud_name is public (it ships in every image URL), so hardcoding it is fine.
// To change provider, swap the URL builder in companyLogoUrl.ts — callers do not care.
export const CLOUDINARY_CLOUD_NAME = "dskksi2dd";
