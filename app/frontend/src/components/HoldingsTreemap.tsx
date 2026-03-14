import { useMemo, useState } from "react";

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
}

function getDeltaColor(deltaPct: number, delta: string): string {
  if (delta === "NEW") return "hsl(var(--positive))";
  if (deltaPct > 20) return "hsl(142, 71%, 40%)";
  if (deltaPct > 5) return "hsl(142, 60%, 35%)";
  if (deltaPct > 0) return "hsl(142, 50%, 30%)";
  if (deltaPct === 0) return "hsl(var(--muted))";
  if (deltaPct > -5) return "hsl(0, 50%, 35%)";
  if (deltaPct > -20) return "hsl(0, 60%, 40%)";
  return "hsl(0, 70%, 45%)";
}

// Simple squarified treemap layout
function squarify(
  items: TreemapItem[],
  width: number,
  height: number
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
    isVertical: boolean
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
    h: number
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
      recurse(
        remaining.slice(row.length),
        remTotal - rowTotal,
        x + stripSize,
        y,
        w - stripSize,
        h
      );
    } else {
      layoutRow(row, rowTotal, x, y, w, stripSize, false);
      recurse(
        remaining.slice(row.length),
        remTotal - rowTotal,
        x,
        y + stripSize,
        w,
        h - stripSize
      );
    }
  }

  recurse(items, total, 0, 0, width, height);
  return rects;
}

export function HoldingsTreemap({ data, onClickTicker, height: propHeight, displayMode = "value" }: Props) {
  const [hoveredTicker, setHoveredTicker] = useState<string | null>(null);

  const containerWidth = 100; // percentage-based
  const containerHeight = propHeight ?? 500; // px

  const rects = useMemo(
    () => squarify(data, containerWidth, containerHeight),
    [data]
  );

  return (
    <div
      className="relative w-full rounded overflow-hidden"
      style={{ height: containerHeight }}
    >
      {rects.map(({ item, x, y, w, h }) => {
        const isHovered = hoveredTicker === item.name;
        const bgColor = getDeltaColor(item.deltaPct, item.delta);
        const isSmall = w < 12 || h < 28;
        const isTiny = w < 8 || h < 20;

        return (
          <div
            key={item.name}
            className="absolute cursor-pointer transition-opacity duration-150 flex flex-col items-center justify-center overflow-hidden"
            style={{
              left: `${x}%`,
              top: y,
              width: `${w}%`,
              height: h,
              backgroundColor: bgColor,
              opacity: isHovered ? 1 : hoveredTicker ? 0.7 : 0.9,
              border: "1px solid hsl(var(--background) / 0.3)",
            }}
            onClick={() => onClickTicker(item.name)}
            onMouseEnter={() => setHoveredTicker(item.name)}
            onMouseLeave={() => setHoveredTicker(null)}
            title={`${item.name} — ${item.company}\n${displayMode === "pct" ? formatTreemapPct(item.value) : formatTreemapValue(item.value)}\nΔ ${item.deltaPct > 0 ? "+" : ""}${item.deltaPct.toFixed(1)}%`}
          >
            <span
              className="font-mono font-bold text-white drop-shadow-sm leading-tight truncate px-0.5"
              style={{ fontSize: Math.max(7, Math.min(14, isSmall ? 8 : w * 0.8)) }}
            >
              {item.name}
            </span>
            {!isSmall && h > 36 && (
              <span className="text-white/70 text-[9px] leading-tight mt-0.5">
                {displayMode === "pct" ? formatTreemapPct(item.value) : formatTreemapValue(item.value)}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}
