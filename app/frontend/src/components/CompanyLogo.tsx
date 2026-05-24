import { useEffect, useRef, useState } from "react";

import { buildLogoUrl } from "@/components/companyLogoUrl";

interface CompanyLogoProps {
  ticker: string;
  size?: number;
  className?: string;
}

/**
 * Deterministic hue from a ticker string, so the same symbol always gets the
 * same colored avatar across the app.
 */
function tickerHue(ticker: string): number {
  let h = 0;
  for (let i = 0; i < ticker.length; i++) {
    h = (h * 31 + ticker.charCodeAt(i)) | 0;
  }
  return Math.abs(h) % 360;
}

/**
 * Renders the company logo for a ticker. On 404 / load error (common for
 * ETFs and small caps that FMP doesn't track), falls back to a colored
 * initial-letter avatar — the ticker is the identifier, so seeing it in the
 * avatar slot is more useful than a blank grey square.
 */
export function CompanyLogo({ ticker, size = 32, className = "" }: CompanyLogoProps) {
  const [failed, setFailed] = useState(false);
  // Native loading="lazy" still fetches with a ~300px viewport margin — Chrome
  // ends up firing dozens of requests as soon as the page mounts. Gate the
  // fetch on actual intersection so a 500-card grid only fetches what's
  // genuinely on screen.
  const placeholderRef = useRef<HTMLDivElement | null>(null);
  const [intersected, setIntersected] = useState(false);
  useEffect(() => {
    if (intersected || !placeholderRef.current) return;
    const el = placeholderRef.current;
    const obs = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) {
          setIntersected(true);
          obs.disconnect();
        }
      },
      { rootMargin: "100px" },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, [intersected]);

  if (!ticker) {
    return (
      <div
        aria-label="Logo placeholder"
        className={`bg-muted rounded ${className}`}
        style={{ width: size, height: size, flexShrink: 0 }}
      />
    );
  }

  if (failed) {
    const hue = tickerHue(ticker);
    const initials = ticker.slice(0, Math.min(4, ticker.length));
    // Font sizing scales with both container and number of letters so 1-letter
    // tickers fill the box and 4-letter tickers still fit without overflow.
    const fontSize = Math.max(8, Math.round((size * 0.9) / Math.max(initials.length, 2)));
    return (
      <div
        role="img"
        aria-label={`${ticker} logo`}
        className={`rounded flex items-center justify-center font-mono font-semibold select-none ${className}`}
        style={{
          width: size,
          height: size,
          flexShrink: 0,
          background: `hsl(${hue} 55% 32%)`,
          color: "white",
          fontSize,
          letterSpacing: initials.length > 2 ? "-0.04em" : "0",
        }}
      >
        {initials}
      </div>
    );
  }

  if (!intersected) {
    return (
      <div
        ref={placeholderRef}
        aria-hidden="true"
        className={`bg-muted/30 rounded ${className}`}
        style={{ width: size, height: size, flexShrink: 0 }}
      />
    );
  }

  return (
    <img
      src={buildLogoUrl(ticker, size)}
      alt={ticker}
      width={size}
      height={size}
      onError={() => setFailed(true)}
      className={`rounded object-contain ${className}`}
      style={{ width: size, height: size, flexShrink: 0 }}
      loading="lazy"
    />
  );
}
