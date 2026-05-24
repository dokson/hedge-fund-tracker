import { CLOUDINARY_CLOUD_NAME, IS_GH_PAGES_MODE } from "@/lib/config";

const FMP_LOGO_BASE = "https://images.financialmodelingprep.com/symbol";

/**
 * Builds the URL for a ticker's company logo. In GH Pages mode we go through
 * Cloudinary's fetch CDN (edge cache + retina-sized transforms); in local dev
 * we hit FMP directly because the Cloudinary account restricts strict-transform
 * fetches to the production referrer domain, which would otherwise 401.
 */
export function buildLogoUrl(ticker: string, size: number): string {
  const source = `${FMP_LOGO_BASE}/${encodeURIComponent(ticker)}.png`;
  if (!IS_GH_PAGES_MODE) return source;
  const transforms = `w_${size * 2},h_${size * 2},c_fit,f_auto,q_auto`;
  return `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/fetch/${transforms}/${source}`;
}
