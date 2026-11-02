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

/** Read source pixels safely; contrast analysis alone uses a tiny sample. */
function readImagePixels(img: HTMLImageElement, sampleSize?: number): Uint8ClampedArray | null {
  if (!img.naturalWidth || !img.naturalHeight) return null;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = sampleSize ? Math.min(img.naturalWidth, sampleSize) : img.naturalWidth;
    canvas.height = sampleSize ? Math.min(img.naturalHeight, sampleSize) : img.naturalHeight;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  } catch {
    return null;
  }
}

/**
 * Whether a loaded image is blank. An image whose pixels cannot be read (no 2D canvas, or a
 * cross-origin image without CORS headers) is never reported blank: only a positive reading
 * of an empty image counts.
 */
export function isBlankImage(img: HTMLImageElement): boolean {
  const rgba = readImagePixels(img);
  return rgba !== null && !hasVisibleInk(rgba);
}

/** White-backed sources keep white; only predominantly light, transparent artwork needs dark. */
export function hasLightTransparentInk(rgba: Uint8ClampedArray): boolean {
  let hasTransparency = false;
  let ink = 0;
  let lightInk = 0;
  for (let i = 0; i < rgba.length; i += 4) {
    const alpha = rgba[i + 3];
    if (alpha <= VISIBLE_ALPHA) {
      hasTransparency = true;
      continue;
    }
    ink += alpha;
    // Downsampled edges of white marks average to light grey, not pure white.
    if (Math.min(rgba[i], rgba[i + 1], rgba[i + 2]) > 190) lightInk += alpha;
  }
  return hasTransparency && ink > 0 && lightInk > ink * 0.4;
}

/** Unreadable pixels leave the clean white plate, never an image-load failure. */
export function imageNeedsDarkPlate(img: HTMLImageElement): boolean {
  const rgba = readImagePixels(img, 32);
  return rgba !== null && hasLightTransparentInk(rgba);
}
