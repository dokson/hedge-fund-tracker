/**
 * Opaque source backgrounds stay untouched; light transparent artwork gets a dark neutral.
 * The image stays hidden while pending, so no plate flashes before the artwork is read.
 */
export const LOGO_PLATE_BACKGROUND = {
  pending: "transparent",
  light: "white",
  dark: "#18181b",
} as const;

export type LogoPlate = keyof typeof LOGO_PLATE_BACKGROUND;
