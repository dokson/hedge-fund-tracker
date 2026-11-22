import { useMemo, useState } from "react";

import { buildFaviconUrls } from "@/components/faviconUrl";
import { useFallbackSrc } from "@/hooks/useFallbackSrc";
import { LOGO_PLATE_BACKGROUND, type LogoPlate } from "@/components/logoPresentation";
import { imageNeedsDarkPlate, isBlankImage } from "@/lib/imageInk";

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
  /** Above-the-fold logo (page header): requested with the page instead of lazily. */
  eager?: boolean;
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
 * Renders the favicon of a hedge fund's website, trying each source in turn (the curated
 * Cloudinary asset, then icon.horse through the CDN, then icon.horse direct), and finally a
 * monogram tile on the neutral chip surface when all fail. The tile is a token surface, not
 * an invented hue: a per-fund colour was a hue outside the token set, and a bare white square
 * read as a broken image.
 */
export function FundLogo({
  fundName,
  url,
  size = 32,
  className = "",
  decorative = true,
  eager = false,
}: FundLogoProps) {
  const candidates = useMemo(() => buildFaviconUrls(url, size), [url, size]);

  const { src, next } = useFallbackSrc(candidates);
  const [plate, setPlate] = useState<LogoPlate>("pending");

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
          fontSize: Math.max(9, Math.round(size * 0.4)),
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
      crossOrigin="anonymous"
      onError={() => {
        setPlate("pending");
        next();
      }}
      onLoad={(e) => {
        if (isBlankImage(e.currentTarget)) {
          setPlate("pending");
          next();
        } else {
          setPlate(imageNeedsDarkPlate(e.currentTarget) ? "dark" : "light");
        }
      }}
      className={`rounded-sm border border-border object-contain p-px transition-opacity duration-150 ${plate === "pending" ? "opacity-0" : "opacity-100"} ${className}`}
      style={{
        width: size,
        height: size,
        flexShrink: 0,
        backgroundColor: LOGO_PLATE_BACKGROUND[plate],
      }}
      loading={eager ? undefined : "lazy"}
    />
  );
}
