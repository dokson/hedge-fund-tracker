/** Largest and smallest label size; below the floor the label is dropped, not shrunk. */
const MAX_FONT = 14;
const MIN_FONT = 11;
/** Average glyph width as a fraction of the font size. */
const CHAR_WIDTH = 0.6;
const LINE_HEIGHT = 1.25;
/** Room the value line under the name takes. */
const VALUE_LINE_PX = 16;
/** Shortest truncated label worth showing, ellipsis included. */
const MIN_TRUNCATED_CHARS = 5;

export interface TreemapLabel {
  lines: string[];
  fontSize: number;
}

/**
 * Fits a tile's name: one line when it fits, else a long multi-word name
 * (a sector such as "Communication Services") goes onto two balanced lines
 * rather than vanishing, and as a last resort the name is cut with an
 * ellipsis at the minimum size (the tooltip carries it in full). Null only when
 * not even a few characters fit.
 */
export function treemapLabel(
  name: string,
  cellPx: number,
  height: number,
  showValue: boolean,
): TreemapLabel | null {
  const usableWidth = cellPx - 4;
  const oneLine = Math.min(
    MAX_FONT,
    usableWidth / Math.max(name.length, 1) / CHAR_WIDTH,
    showValue ? height * 0.45 : height * 0.7,
  );
  if (oneLine >= MIN_FONT) return { lines: [name], fontSize: oneLine };

  const truncated = (): TreemapLabel | null => {
    const fit = Math.floor(usableWidth / (MIN_FONT * CHAR_WIDTH));
    const lineFits = (showValue ? height * 0.45 : height * 0.7) >= MIN_FONT;
    if (!lineFits || fit < MIN_TRUNCATED_CHARS) return null;
    return { lines: [`${name.slice(0, fit - 1)}…`], fontSize: MIN_FONT };
  };

  const words = name.split(" ").filter(Boolean);
  if (words.length < 2) return truncated();
  let best: [string, string] | null = null;
  for (let i = 1; i < words.length; i++) {
    const split: [string, string] = [words.slice(0, i).join(" "), words.slice(i).join(" ")];
    const longest = Math.max(split[0].length, split[1].length);
    if (!best || longest < Math.max(best[0].length, best[1].length)) best = split;
  }
  if (!best) return truncated();
  const longest = Math.max(best[0].length, best[1].length);
  const twoLines = Math.min(
    MAX_FONT,
    usableWidth / longest / CHAR_WIDTH,
    (height - (showValue ? VALUE_LINE_PX : 0) - 4) / 2 / LINE_HEIGHT,
  );
  return twoLines >= MIN_FONT ? { lines: best, fontSize: twoLines } : truncated();
}
