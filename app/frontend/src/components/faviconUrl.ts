import { CLOUDINARY_CLOUD_NAME, IS_GH_PAGES_MODE } from "@/lib/config";

const ICON_HORSE_BASE = "https://icon.horse/icon";
const CLOUDINARY_FUND_FAVICON_FOLDER = "funds/favicons";

function hostOf(url: string | undefined | null): string | null {
  if (!url) return null;
  try {
    return new URL(url).hostname.replace(/^www\./, "") || null;
  } catch {
    return null;
  }
}

/**
 * URL of the curated Cloudinary-stored favicon for this fund's host, if we
 * uploaded one. Callers should use this as the primary <img src> and fall
 * back via onError when the asset is missing (404).
 */
export function buildCuratedFaviconUrl(url: string | undefined | null): string | null {
  const host = hostOf(url);
  if (!host) return null;
  return `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/upload/${CLOUDINARY_FUND_FAVICON_FOLDER}/${encodeURIComponent(host)}.png`;
}

/**
 * Generic fallback: icon.horse for the fund's host, proxied through
 * Cloudinary's fetch CDN in GH Pages mode (in dev we hit icon.horse
 * directly because Cloudinary's strict referrer policy 401s from
 * localhost). Returns null when the URL is missing or unparseable.
 */
export function buildFaviconUrl(url: string | undefined | null, size: number): string | null {
  const host = hostOf(url);
  if (!host) return null;
  const source = `${ICON_HORSE_BASE}/${encodeURIComponent(host)}`;
  if (!IS_GH_PAGES_MODE) return source;
  const retina = size * 2;
  const transforms = `w_${retina},h_${retina},c_fit,f_auto,q_auto`;
  return `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/fetch/${transforms}/${encodeURIComponent(source)}`;
}
