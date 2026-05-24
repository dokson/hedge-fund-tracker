import { CLOUDINARY_CLOUD_NAME, IS_GH_PAGES_MODE } from "@/lib/config";

const GOOGLE_FAVICON_BASE = "https://www.google.com/s2/favicons";

/**
 * Builds the URL for a fund website's favicon. Google's S2 service is used as
 * the source — it never 404s, returning a generic globe icon for unknown
 * domains. In GH Pages mode we proxy through Cloudinary's fetch CDN for edge
 * caching + retina sizing, mirroring the company-logo pipeline. In local dev
 * we hit Google directly because Cloudinary's strict-referrer policy would
 * otherwise 401 from localhost.
 *
 * Returns null if the input URL is missing or unparseable, so callers can
 * decide whether to render anything at all.
 */
export function buildFaviconUrl(url: string | undefined | null, size: number): string | null {
  if (!url) return null;
  let host: string;
  try {
    host = new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
  if (!host) return null;
  const source = `${GOOGLE_FAVICON_BASE}?domain=${encodeURIComponent(host)}&sz=${size * 2}`;
  if (!IS_GH_PAGES_MODE) return source;
  const transforms = `w_${size * 2},h_${size * 2},c_fit,f_auto,q_auto`;
  return `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/fetch/${transforms}/${encodeURIComponent(source)}`;
}
