import { cloudinaryFetch } from "@/components/cloudinaryFetch";
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
 * The URLs to try for a fund's logo, in order: the curated favicon we uploaded to Cloudinary
 * for its host (no transform, so strict transformations never refuse it), then icon.horse for
 * the host, through the Cloudinary fetch CDN in GH Pages mode and then direct (icon.horse
 * sends CORS headers). In local dev icon.horse is hit directly: Cloudinary's referrer policy
 * 401s from localhost. Empty when the URL is missing or unparseable.
 */
export function buildFaviconUrls(url: string | undefined | null, size: number): string[] {
  const host = hostOf(url);
  if (!host) return [];
  const curated = `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/upload/${CLOUDINARY_FUND_FAVICON_FOLDER}/${encodeURIComponent(host)}.png`;
  const source = `${ICON_HORSE_BASE}/${encodeURIComponent(host)}`;
  return IS_GH_PAGES_MODE
    ? [curated, cloudinaryFetch(encodeURIComponent(source), size), source]
    : [curated, source];
}
