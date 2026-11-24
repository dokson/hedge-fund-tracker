import { cloudinaryFetch } from "@/components/cloudinaryFetch";
import curatedTickers from "@/data/curatedLogos.json";
import { CLOUDINARY_CLOUD_NAME, IS_GH_PAGES_MODE } from "@/lib/config";

const FMP_LOGO_BASE = "https://images.financialmodelingprep.com/symbol";
/** Tickers with a logo uploaded to Cloudinary (`pipenv run gen-logos`). */
const CURATED_TICKERS: ReadonlySet<string> = new Set(curatedTickers);

/**
 * The URLs to try for a ticker's company logo, in order. A logo we uploaded to Cloudinary
 * comes first, for the tickers its manifest lists (FMP has none for them; no transform, so
 * strict transformations never refuse it). Then, in GH Pages mode, the Cloudinary fetch CDN
 * (edge cache, retina size), then FMP itself, which also sends CORS headers, so a CDN refusal
 * never costs the logo. In local dev only FMP: the Cloudinary account restricts fetches to the
 * production referrer, which would 401 from localhost.
 */
export function buildLogoUrls(ticker: string, size: number): string[] {
  const source = `${FMP_LOGO_BASE}/${encodeURIComponent(ticker)}.png`;
  const sources = IS_GH_PAGES_MODE ? [cloudinaryFetch(source, size), source] : [source];
  if (!CURATED_TICKERS.has(ticker)) return sources;
  return [
    `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/upload/stocks/logos/${encodeURIComponent(ticker)}.png`,
    ...sources,
  ];
}
