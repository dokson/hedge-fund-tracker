/**
 * Stretched-link pattern for clickable cards: the card is `relative`, one real
 * link inside it spreads its hit area over the whole card via `::after`, and
 * any other control in the card is lifted above that overlay.
 */
export const STRETCHED_CARD = "relative";
export const STRETCHED_LINK =
  "after:absolute after:inset-0 focus-visible:outline-none focus-visible:after:outline-2 focus-visible:after:-outline-offset-2 focus-visible:after:outline-ring";
export const ABOVE_STRETCHED_LINK = "relative z-10";
