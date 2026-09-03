import { useMemo, useState } from "react";

import { buildCuratedFaviconUrl, buildFaviconUrl } from "@/components/faviconUrl";

interface FundLogoProps {
  /** Short canonical fund name (CSV `Fund` column) — used for the fallback avatar. */
  fundName: string;
  /** Fund website URL — passed to the favicon URL builders. Falls back if missing/unparseable. */
  url?: string | null;
  size?: number;
  className?: string;
  /**
   * Default. The favicon always sits beside the fund name today, so naming it
   * repeats the adjacent text (SC 1.1.1, axe `image-redundant-alt`). Pass
   * `false` only where the logo stands alone.
   */
  decorative?: boolean;
}

/** Two initials at most: "Baupost Group" reads better than a lone "B". */
function fundInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  return words
    .slice(0, 2)
    .map((w) => w[0] ?? "")
    .join("")
    .toUpperCase();
}

/**
 * Renders the favicon of a hedge fund's website. Tries the curated
 * Cloudinary-stored asset first, falls back to icon.horse (also via
 * Cloudinary in GH Pages mode), and finally to a monogram tile on the neutral
 * chip surface when both fail. The tile is a token surface, not an invented
 * hue: a per-fund colour was a hue outside the token set, and a bare white
 * square read as a broken image.
 */
export function FundLogo({
  fundName,
  url,
  size = 32,
  className = "",
  decorative = true,
}: FundLogoProps) {
  const candidates = useMemo(() => {
    const list: string[] = [];
    const curated = buildCuratedFaviconUrl(url);
    if (curated) list.push(curated);
    const generic = buildFaviconUrl(url, size);
    if (generic) list.push(generic);
    return list;
  }, [url, size]);

  const [index, setIndex] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const src = candidates[index];

  if (!src) {
    return (
      <div
        role={decorative ? undefined : "img"}
        aria-hidden={decorative || undefined}
        aria-label={decorative ? undefined : `${fundName} logo`}
        className={`flex items-center justify-center rounded-sm border border-border bg-muted font-semibold text-muted-foreground select-none ${className}`}
        style={{
          width: size,
          height: size,
          flexShrink: 0,
          fontSize: Math.round(size * 0.4),
          letterSpacing: "-0.02em",
        }}
      >
        {fundInitials(fundName)}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={decorative ? "" : fundName}
      width={size}
      height={size}
      onError={() => setIndex((i) => i + 1)}
      onLoad={() => setLoaded(true)}
      className={`rounded-sm border border-border object-contain ${loaded ? "bg-white p-px" : "bg-card"} ${className}`}
      style={{ width: size, height: size, flexShrink: 0 }}
      loading="lazy"
    />
  );
}
