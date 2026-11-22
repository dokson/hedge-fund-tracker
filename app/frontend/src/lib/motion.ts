/**
 * Whether the OS asks for reduced motion, for the motion CSS cannot reach (smooth
 * `scrollIntoView`, chart animations). `matchMedia` is absent in some non-browser
 * environments (jsdom), where this reads as "reduce".
 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** The scroll behaviour to request: smooth unless the OS asks for reduced motion. */
export function scrollBehavior(): ScrollBehavior {
  return prefersReducedMotion() ? "auto" : "smooth";
}
