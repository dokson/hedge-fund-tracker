import { BASE_PATH } from "@/lib/config";

/**
 * The cyborg-bull mark. A 224px webp (~9 KB) covers every on-screen size up to
 * the 112px hero at 2x; the 512px logo.png stays for social cards and JSON-LD.
 * Explicit width/height reserve the box so the image never shifts the layout.
 */
export function BrandLogo({
  size,
  alt = "",
  priority = false,
  className,
}: {
  size: number;
  alt?: string;
  priority?: boolean;
  className?: string;
}) {
  return (
    <img
      src={`${BASE_PATH}/logo-mark.webp`}
      alt={alt}
      width={size}
      height={size}
      decoding="async"
      fetchPriority={priority ? "high" : undefined}
      className={className}
    />
  );
}
