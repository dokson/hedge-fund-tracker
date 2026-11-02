/** Largest and smallest label size; below the floor the label is dropped, not shrunk. */
const MAX_FONT = 14;
const MIN_FONT = 11;
/** Conservative glyph width, with room around the label inside the tile. */
const CHAR_WIDTH = 0.68;
const LINE_HEIGHT = 1.25;
const VALUE_LINE_PX = 16;

export interface TreemapLabel {
  lines: string[];
  fontSize: number;
}

/**
 * Fits complete names on one or two balanced lines. Tiles below the readable
 * size floor, or names that cannot fit at the minimum font size, stay unlabelled;
 * the interactive tooltip always carries the full name and value.
 */
export function treemapLabel(
  name: string,
  cellPx: number,
  height: number,
  showValue: boolean,
): TreemapLabel | null {
  if (cellPx < 44 || height < (showValue ? 40 : 24)) return null;
  const usableWidth = cellPx - 8;
  const oneLine = Math.min(
    MAX_FONT,
    usableWidth / Math.max(name.length, 1) / CHAR_WIDTH,
    showValue ? height * 0.45 : height * 0.7,
  );
  if (oneLine >= MIN_FONT) return { lines: [name], fontSize: oneLine };

  const words = name.split(" ").filter(Boolean);
  if (words.length < 2) return null;
  let best: [string, string] | null = null;
  for (let i = 1; i < words.length; i++) {
    const split: [string, string] = [words.slice(0, i).join(" "), words.slice(i).join(" ")];
    const longest = Math.max(split[0].length, split[1].length);
    if (!best || longest < Math.max(best[0].length, best[1].length)) best = split;
  }
  if (!best) return null;
  const longest = Math.max(best[0].length, best[1].length);
  const twoLines = Math.min(
    MAX_FONT,
    usableWidth / longest / CHAR_WIDTH,
    (height - (showValue ? VALUE_LINE_PX : 0) - 4) / 2 / LINE_HEIGHT,
  );
  return twoLines >= MIN_FONT ? { lines: best, fontSize: twoLines } : null;
}
