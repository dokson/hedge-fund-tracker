import { CLOUDINARY_CLOUD_NAME } from "@/lib/config";

/**
 * A remote image through Cloudinary's fetch CDN, sized for retina (twice the display size).
 *
 * The account runs strict transformations: only the transforms it already allows are served,
 * and these all use `f_auto` (an explicit `f_webp` is refused). `f_auto` can still resolve to
 * a variant the account refuses (JPEG XL for Chrome at a size never requested before, a 401),
 * so callers always list the original source after this URL: a refused variant never costs
 * a logo that exists.
 */
export function cloudinaryFetch(source: string, size: number): string {
  const px = size * 2;
  return `https://res.cloudinary.com/${CLOUDINARY_CLOUD_NAME}/image/fetch/w_${px},h_${px},c_fit,f_auto,q_auto/${source}`;
}
