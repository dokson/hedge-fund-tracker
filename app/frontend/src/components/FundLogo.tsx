import { useState } from "react";

import { buildFaviconUrl } from "@/components/faviconUrl";

interface FundLogoProps {
  /** Short canonical fund name (CSV `Fund` column) — used for the fallback avatar. */
  fundName: string;
  /** Fund website URL — passed to buildFaviconUrl. Falls back if missing/unparseable. */
  url?: string | null;
  size?: number;
  className?: string;
}

function fundHue(name: string): number {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) | 0;
  return Math.abs(h) % 360;
}

/**
 * Renders the favicon of a hedge fund's website (proxied through the same
 * Cloudinary pipeline used for company logos in GH Pages mode, direct to
 * Google S2 in dev). On 404 / error / missing URL, falls back to a colored
 * initial-letter avatar — keeps the visual slot filled and the fund
 * recognisable even without a website.
 */
export function FundLogo({ fundName, url, size = 32, className = "" }: FundLogoProps) {
  const [failed, setFailed] = useState(false);
  const src = buildFaviconUrl(url, size);

  if (!src || failed) {
    const hue = fundHue(fundName);
    const initials = fundName.slice(0, Math.min(2, fundName.length)).toUpperCase();
    return (
      <div
        role="img"
        aria-label={`${fundName} logo`}
        className={`rounded flex items-center justify-center font-sans font-semibold select-none ${className}`}
        style={{
          width: size,
          height: size,
          flexShrink: 0,
          background: `hsl(${hue} 55% 32%)`,
          color: "white",
          fontSize: Math.round(size * 0.42),
          letterSpacing: "-0.02em",
        }}
      >
        {initials}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={fundName}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className={`rounded object-contain ${className}`}
      style={{ width: size, height: size, flexShrink: 0 }}
      loading="lazy"
    />
  );
}
