import { cloudinaryFetch } from "@/components/cloudinaryFetch";
import curatedHosts from "@/data/curatedFavicons.json";
import { CLOUDINARY_CLOUD_NAME, IS_GH_PAGES_MODE } from "@/lib/config";

const ICON_HORSE_BASE = "https://icon.horse/icon";
const CLOUDINARY_FUND_FAVICON_FOLDER = "funds/favicons";
/** Hosts with a favicon uploaded to Cloudinary (`pipenv run gen-logos`). */
const CURATED_HOSTS: ReadonlySet<string> = new Set(curatedHosts);

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
 * 401s from localhost. The curated favicon is only listed for a host in the manifest: asking
 * for a missing one logs a 404 in the console. Empty when the URL is missing or unparseable.
 */
export function buildFaviconUrls(url: string | undefined | null, size: number): string[] {
  const host = hostOf(url);
  if (!host) return [];
  const source = `${ICON_HORSE_BASE}/${encodeURIComponent(host)}`;
  const sources = IS_GH_PAGES_MODE
    ? [cloudinaryFetch(encodeURIComponent(source), size), source]
    : [source];
  if (!CURATED_HOSTS.has(host)) return sources;
  return [
    `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/upload/${CLOUDINARY_FUND_FAVICON_FOLDER}/${encodeURIComponent(host)}.png`,
    ...sources,
  ];
}
