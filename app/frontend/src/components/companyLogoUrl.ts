import { cloudinaryFetch } from "@/components/cloudinaryFetch";
import { IS_GH_PAGES_MODE } from "@/lib/config";

const FMP_LOGO_BASE = "https://images.financialmodelingprep.com/symbol";

/**
 * The URLs to try for a ticker's company logo, in order. In GH Pages mode the Cloudinary
 * fetch CDN first (edge cache, retina size), then FMP itself, which also sends CORS headers,
 * so a CDN refusal never costs the logo. In local dev only FMP: the Cloudinary account
 * restricts fetches to the production referrer, which would 401 from localhost.
 */
export function buildLogoUrls(ticker: string, size: number): string[] {
  const source = `${FMP_LOGO_BASE}/${encodeURIComponent(ticker)}.png`;
  return IS_GH_PAGES_MODE ? [cloudinaryFetch(source, size), source] : [source];
}
