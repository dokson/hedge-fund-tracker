import { useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { formatPct } from "@/lib/dataService";
import { tokenAlpha } from "@/lib/seriesColors";

function formatTreemapValue(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function formatTreemapPct(n: number): string {
  return `${n.toFixed(1)}%`;
}

interface TreemapItem {
  name: string;
  company: string;
  value: number;
  deltaPct: number;
  delta: string;
}

interface Props {
  data: TreemapItem[];
  onClickTicker: (ticker: string) => void;
  height?: number;
  displayMode?: "value" | "pct";
  /**
   * When set, cells whose name differs from it are dimmed — a visual cue that a
   * filter is active while keeping every cell clickable to switch the selection.
   * Passing it (even as null) turns the tiles into toggles: they carry
   * `aria-pressed`, and the active one takes the selection ring.
   */
  activeName?: string | null;
  /**
   * When set, cells whose name is not in it are dimmed. Used to project another
   * treemap's selection onto this one (sector → the stocks in that sector).
   */
  highlightNames?: ReadonlySet<string> | null;
}

// Alpha stays at or under 0.55 so `text-foreground` reads on the tile in both
// themes; the magnitude is carried by the step, not by a second hue.
function getDeltaColor(deltaPct: number, delta: string): string {
  if (delta === "NEW") return tokenAlpha("positive", 0.55);
  if (deltaPct > 20) return tokenAlpha("positive", 0.55);
  if (deltaPct > 5) return tokenAlpha("positive", 0.38);
  if (deltaPct > 0) return tokenAlpha("positive", 0.22);
  if (deltaPct === 0) return "hsl(var(--muted))";
  if (deltaPct > -5) return tokenAlpha("negative", 0.22);
  if (deltaPct > -20) return tokenAlpha("negative", 0.38);
  return tokenAlpha("negative", 0.55);
}

interface TooltipState {
  item: TreemapItem;
  x: number;
  y: number;
}

// Portaled so the treemap's overflow-hidden never clips it.
function TreemapTooltip({
  tip,
  displayMode,
}: {
  tip: TooltipState | null;
  displayMode: "value" | "pct";
}) {
  if (!tip) return null;

  const { item, x, y } = tip;
  const isNew = item.delta === "NEW";
  const up = item.deltaPct > 0 || isNew;
  const down = item.deltaPct < 0;
  const accent = getDeltaColor(item.deltaPct, item.delta);

  // Flip by cursor quadrant so the panel never spills off-screen.
  const OFFSET = 18;
  const flipX = x > window.innerWidth * 0.6;
  const flipY = y > window.innerHeight * 0.55;
  const left = flipX ? x - OFFSET : x + OFFSET;
  const top = flipY ? y - OFFSET : y + OFFSET;
  const translate = `translate(${flipX ? "-100%" : "0"}, ${flipY ? "-100%" : "0"})`;

  const noChange = !isNew && item.deltaPct === 0;
  const deltaLabel = isNew ? "NEW" : noChange ? "NO CHANGE" : formatPct(item.deltaPct, true);
  const deltaTone = isNew
    ? "text-[hsl(var(--positive))]"
    : down
      ? "text-[hsl(var(--negative))]"
      : up
        ? "text-[hsl(var(--positive))]"
        : "text-muted-foreground";

  const DeltaIcon = isNew || up ? TrendingUp : down ? TrendingDown : Minus;

  return createPortal(
    <div className="pointer-events-none fixed z-[60]" style={{ left, top, transform: translate }}>
      <div className="flex overflow-hidden rounded-md border border-border bg-popover text-xs text-popover-foreground shadow-md">
        <span aria-hidden className="w-1 shrink-0" style={{ backgroundColor: accent }} />
        <div className="px-3 py-2">
          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold">{item.name}</span>
            <span
              className={`ml-auto inline-flex items-center gap-1 text-[11px] font-semibold tabular-nums ${deltaTone}`}
            >
              <DeltaIcon className="h-3 w-3" aria-hidden="true" />
              {deltaLabel}
            </span>
          </div>
          {item.company && item.company !== item.name && (
            <div className="mt-0.5 max-w-[14rem] truncate text-[11px] text-muted-foreground">
              {item.company}
            </div>
          )}
          <div className="mt-1.5 text-base font-semibold tabular-nums">
            {displayMode === "pct" ? formatTreemapPct(item.value) : formatTreemapValue(item.value)}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

// Simple squarified treemap layout
function squarify(
  items: TreemapItem[],
  width: number,
  height: number,
): { item: TreemapItem; x: number; y: number; w: number; h: number }[] {
  const total = items.reduce((s, d) => s + d.value, 0);
  if (total === 0 || items.length === 0) return [];

  const rects: { item: TreemapItem; x: number; y: number; w: number; h: number }[] = [];

  function layoutRow(
    row: TreemapItem[],
    rowTotal: number,
    x: number,
    y: number,
    w: number,
    h: number,
    isVertical: boolean,
  ) {
    let offset = 0;
    for (const item of row) {
      const fraction = item.value / rowTotal;
      if (isVertical) {
        const itemH = h * fraction;
        rects.push({ item, x, y: y + offset, w, h: itemH });
        offset += itemH;
      } else {
        const itemW = w * fraction;
        rects.push({ item, x: x + offset, y, w: itemW, h });
        offset += itemW;
      }
    }
  }

  function recurse(
    remaining: TreemapItem[],
    remTotal: number,
    x: number,
    y: number,
    w: number,
    h: number,
  ) {
    if (remaining.length === 0) return;
    if (remaining.length === 1) {
      rects.push({ item: remaining[0], x, y, w, h });
      return;
    }

    const isVertical = w >= h;
    const mainDim = isVertical ? w : h;
    const crossDim = isVertical ? h : w;

    // Greedily add items to the current row
    let row: TreemapItem[] = [];
    let rowTotal = 0;
    let bestAspect = Infinity;

    for (let i = 0; i < remaining.length; i++) {
      const candidate = [...row, remaining[i]];
      const candidateTotal = rowTotal + remaining[i].value;
      const stripSize = (candidateTotal / remTotal) * mainDim;

      // Worst aspect ratio in this candidate row
      let worstAspect = 0;
      for (const item of candidate) {
        const fraction = item.value / candidateTotal;
        const itemCross = crossDim * fraction;
        const aspect = Math.max(stripSize / itemCross, itemCross / stripSize);
        worstAspect = Math.max(worstAspect, aspect);
      }

      if (worstAspect <= bestAspect || row.length === 0) {
        row = candidate;
        rowTotal = candidateTotal;
        bestAspect = worstAspect;
      } else {
        break;
      }
    }

    const stripFraction = rowTotal / remTotal;
    const stripSize = stripFraction * mainDim;

    if (isVertical) {
      layoutRow(row, rowTotal, x, y, stripSize, h, true);
      recurse(remaining.slice(row.length), remTotal - rowTotal, x + stripSize, y, w - stripSize, h);
    } else {
      layoutRow(row, rowTotal, x, y, w, stripSize, false);
      recurse(remaining.slice(row.length), remTotal - rowTotal, x, y + stripSize, w, h - stripSize);
    }
  }

  recurse(items, total, 0, 0, width, height);
  return rects;
}

export function HoldingsTreemap({
  data,
  onClickTicker,
  height: propHeight,
  displayMode = "value",
  activeName,
  highlightNames = null,
}: Props) {
  // `activeName` present at all (null included) means the tiles are toggles.
  const selectable = activeName !== undefined;
  const active = activeName ?? null;
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null);
  const [tip, setTip] = useState<TooltipState | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerPx, setContainerPx] = useState(0);

  const containerWidth = 100; // percentage-based
  const containerHeight = propHeight ?? 500; // px

  // Real px width: the same width % is far narrower in the side-by-side Sector
  // Map than the wide Holdings Map, so font sizing needs actual pixels.
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    setContainerPx(el.clientWidth);
    const ro = new ResizeObserver((entries) => {
      setContainerPx(entries[0].contentRect.width);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const rects = useMemo(
    () => squarify(data, containerWidth, containerHeight),
    [data, containerHeight],
  );

  // Each tile carries its own hairline, so the gaps between them read as a
  // 1px rule and the tile keeps the site's 2px corner.
  return (
    <>
      <div
        ref={containerRef}
        className="relative w-full overflow-hidden"
        style={{ height: containerHeight }}
      >
        {rects.map(({ item, x, y, w, h }) => {
          const isHovered = hoveredTicker === item.name;
          const isSelected = active != null && item.name === active;
          const isDimmed =
            (active != null && !isSelected) ||
            (highlightNames != null && !highlightNames.has(item.name));
          const bgColor = getDeltaColor(item.deltaPct, item.delta);
          const showValue = h > 40;

          // Bound font by cell px width (≈0.6em/char) and height; fall back
          // to the width-% heuristic until the container is measured. Below the
          // 11px floor the label is dropped rather than shrunk.
          const cellPx = (w / 100) * containerPx;
          const fitSize = containerPx
            ? Math.min(
                14,
                (cellPx - 4) / Math.max(item.name.length, 1) / 0.6,
                showValue ? h * 0.45 : h * 0.7,
              )
            : Math.min(14, w * 0.8);
          const showLabel = fitSize >= 11;
          const fontSize = Math.max(11, fitSize);

          return (
            <button
              type="button"
              key={item.name}
              aria-label={item.name}
              aria-pressed={selectable ? isSelected : undefined}
              className="absolute flex flex-col items-center justify-center overflow-hidden rounded-sm border border-border text-foreground transition-[opacity,filter,box-shadow] duration-[120ms]"
              style={{
                left: `${x}%`,
                top: y,
                width: `${w}%`,
                height: h,
                backgroundColor: bgColor,
                opacity: isHovered ? 1 : isDimmed ? 0.25 : hoveredTicker ? 0.7 : 1,
                // Dimming desaturates too, so the delta hue does not compete
                // with the tiles that are still in the filter.
                filter: isDimmed && !isHovered ? "saturate(0.25)" : undefined,
                // Inset, so the container's overflow-hidden cannot clip it.
                boxShadow: isSelected ? "inset 0 0 0 2px hsl(var(--primary))" : undefined,
              }}
              onClick={() => onClickTicker(item.name)}
              onMouseEnter={() => setHoveredTicker(item.name)}
              onMouseMove={(e) => setTip({ item, x: e.clientX, y: e.clientY })}
              onMouseLeave={() => {
                setHoveredTicker(null);
                setTip(null);
              }}
            >
              {showLabel && (
                <span
                  className="max-w-full truncate px-0.5 font-semibold leading-tight"
                  style={{ fontSize }}
                >
                  {item.name}
                </span>
              )}
              {showLabel && showValue && (
                // Full foreground, not muted and not faded: on the strongest
                // delta tints the muted tone is 1.9:1 and even foreground at
                // 80% is 3.6:1. At 100% the worst tile is 4.65:1. Size and
                // weight carry the hierarchy instead.
                <span className="mt-0.5 text-[11px] leading-tight text-foreground">
                  {displayMode === "pct"
                    ? formatTreemapPct(item.value)
                    : formatTreemapValue(item.value)}
                </span>
              )}
            </button>
          );
        })}
      </div>
      <TreemapTooltip tip={tip} displayMode={displayMode} />
    </>
  );
}
