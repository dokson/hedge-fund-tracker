import { useMemo, useState } from "react";

import { buildCuratedFaviconUrl, buildFaviconUrl } from "@/components/faviconUrl";

interface FundLogoProps {
  /** Short canonical fund name (CSV `Fund` column) — used for the fallback avatar. */
  fundName: string;
  /** Fund website URL — passed to the favicon URL builders. Falls back if missing/unparseable. */
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
 * Renders the favicon of a hedge fund's website. Tries the curated
 * Cloudinary-stored asset first, falls back to icon.horse (also via
 * Cloudinary in GH Pages mode), and finally to a colored initial-letter
 * avatar when both fail.
 */
export function FundLogo({ fundName, url, size = 32, className = "" }: FundLogoProps) {
  const candidates = useMemo(() => {
    const list: string[] = [];
    const curated = buildCuratedFaviconUrl(url);
    if (curated) list.push(curated);
    const generic = buildFaviconUrl(url, size);
    if (generic) list.push(generic);
    return list;
  }, [url, size]);

  const [index, setIndex] = useState(0);
  const src = candidates[index];

  if (!src) {
    const hue = fundHue(fundName);
    const initials = fundName.slice(0, 1).toUpperCase();
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
          fontSize: Math.round(size * 0.55),
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
      onError={() => setIndex((i) => i + 1)}
      className={`rounded object-contain ${className}`}
      style={{ width: size, height: size, flexShrink: 0 }}
      loading="lazy"
    />
  );
}
