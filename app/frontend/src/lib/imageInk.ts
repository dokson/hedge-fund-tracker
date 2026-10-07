/** Alpha at or below this reads as transparent. */
const VISIBLE_ALPHA = 16;
/** A channel above this reads as white, which vanishes on the white logo tile. */
const WHITE_CHANNEL = 245;

/**
 * Whether RGBA pixel data draws anything visible on a white tile: at least one pixel that is
 * neither (nearly) transparent nor (nearly) white.
 */
export function hasVisibleInk(rgba: Uint8ClampedArray): boolean {
  for (let i = 0; i < rgba.length; i += 4) {
    const isTransparent = rgba[i + 3] <= VISIBLE_ALPHA;
    const isWhite =
      rgba[i] > WHITE_CHANNEL && rgba[i + 1] > WHITE_CHANNEL && rgba[i + 2] > WHITE_CHANNEL;
    if (!isTransparent && !isWhite) return true;
  }
  return false;
}

/**
 * Whether a loaded image is blank. An image whose pixels cannot be read (no 2D canvas, or a
 * cross-origin image without CORS headers) is never reported blank: only a positive reading
 * of an empty image counts.
 */
export function isBlankImage(img: HTMLImageElement): boolean {
  if (!img.naturalWidth || !img.naturalHeight) return false;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = img.naturalWidth;
    canvas.height = img.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return false;
    ctx.drawImage(img, 0, 0);
    return !hasVisibleInk(ctx.getImageData(0, 0, canvas.width, canvas.height).data);
  } catch {
    return false;
  }
}
