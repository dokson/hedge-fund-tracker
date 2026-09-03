import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useElementSize } from "@/hooks/useElementSize";
import {
  AreaChart,
  Area,
  CartesianGrid,
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ReferenceArea,
  type MouseHandlerDataParam,
  type TooltipContentProps,
} from "recharts";
import { Loader2, TrendingUp, TrendingDown, Activity, BarChart3 } from "lucide-react";
import { API_BASE } from "@/lib/config";
import { GRID, NEGATIVE, NEUTRAL, POSITIVE, chartAnimationActive } from "@/lib/seriesColors";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { PanelTitle } from "@/components/ui/PanelTitle";

type RangeKey = "YTD" | "1Y" | "3Y" | "5Y" | "MAX";
type ChartMode = "area" | "candles";
type Candle = { date: string; open: number; high: number; low: number; close: number };
type CandleWithRange = Candle & { range: [number, number] };

const RANGES: ReadonlyArray<{ key: RangeKey; label: string; period: string }> = [
  { key: "YTD", label: "YTD", period: "ytd" },
  { key: "1Y", label: "1Y", period: "1y" },
  { key: "3Y", label: "3Y", period: "3y" },
  { key: "5Y", label: "5Y", period: "5y" },
  { key: "MAX", label: "Max", period: "max" },
];

const UP_COLOR = POSITIVE;
const DOWN_COLOR = NEGATIVE;
const AXIS_TICK = { fill: NEUTRAL, fontSize: 11 };
const CURSOR = { stroke: NEUTRAL, strokeOpacity: 0.4, strokeDasharray: "2 4" };

async function fetchPriceHistory(ticker: string, period: string): Promise<Candle[]> {
  if (!API_BASE) throw new Error("offline");
  const res = await fetch(
    `${API_BASE}/api/stocks/${encodeURIComponent(ticker)}/history?range=${period}`,
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = (await res.json()) as { points?: Candle[] };
  return data.points ?? [];
}

const fmtCurrency = (v: number) => {
  if (Math.abs(v) >= 1000) return `$${(v / 1000).toFixed(1)}k`;
  return `$${v.toFixed(2)}`;
};

const fmtDateShort = (iso: string) => {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
};

const fmtDateFull = (iso: string) => {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" });
};

type CandleShapeProps = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: Candle;
};

/**
 * The Bar uses `[low, high]` as its dataKey, so recharts gives us:
 *   y      = pixel position of `high`
 *   y+height = pixel position of `low`
 * From that we derive a y-scale and place the open/close rectangle precisely.
 */
function Candlestick({ x = 0, y = 0, width = 0, height = 0, payload }: CandleShapeProps) {
  if (!payload || width <= 0 || height <= 0) return null;
  const { open, close, high, low } = payload;
  if (open == null || close == null || high == null || low == null) return null;
  const range = high - low;
  if (range <= 0) return null;

  const pxPerUnit = height / range;
  const yHigh = y;
  const yLow = y + height;
  const yOpen = yHigh + (high - open) * pxPerUnit;
  const yClose = yHigh + (high - close) * pxPerUnit;

  const isUp = close >= open;
  const color = isUp ? UP_COLOR : DOWN_COLOR;
  const bodyTop = Math.min(yOpen, yClose);
  const bodyHeight = Math.max(1, Math.abs(yClose - yOpen));
  const candleW = Math.max(2, width * 0.7);
  const cx = x + width / 2;

  // Let mouse events pass through to the chart so drag-to-select works.
  return (
    <g pointerEvents="none">
      <line x1={cx} x2={cx} y1={yHigh} y2={yLow} stroke={color} strokeWidth={1} />
      <rect
        x={cx - candleW / 2}
        y={bodyTop}
        width={candleW}
        height={bodyHeight}
        fill={color}
        stroke={color}
      />
    </g>
  );
}

type Selection = { start: Candle; end: Candle };

export function StockPriceChart({ ticker, staticData }: { ticker: string; staticData?: Candle[] }) {
  const [range, setRange] = useState<RangeKey>("5Y");
  const [mode, setMode] = useState<ChartMode>("candles");
  const period = RANGES.find((r) => r.key === range)!.period;
  const [containerRef, size] = useElementSize();
  const [selection, setSelection] = useState<Selection | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  // Reset selection when ticker or range changes (React-idiomatic state-on-change pattern)
  const resetKey = `${ticker}|${period}`;
  const [lastResetKey, setLastResetKey] = useState(resetKey);
  if (lastResetKey !== resetKey) {
    setLastResetKey(resetKey);
    setSelection(null);
    setIsDragging(false);
  }

  const lookupCandle = (label: string | number | undefined) =>
    label != null ? (series.find((s) => s.date === label) ?? null) : null;

  const handleMouseDown = (e: MouseHandlerDataParam) => {
    const p = lookupCandle(e.activeLabel);
    if (!p) return;
    setSelection({ start: p, end: p });
    setIsDragging(true);
  };

  const handleMouseMove = (e: MouseHandlerDataParam) => {
    if (!isDragging) return;
    const p = lookupCandle(e.activeLabel);
    if (!p) return;
    setSelection((s) => (s ? { ...s, end: p } : null));
  };

  const handleMouseUp = () => setIsDragging(false);

  // Release drag even if pointer is released outside the chart
  useEffect(() => {
    if (!isDragging) return;
    const onUp = () => setIsDragging(false);
    window.addEventListener("mouseup", onUp);
    return () => window.removeEventListener("mouseup", onUp);
  }, [isDragging]);

  const filteredStatic = useMemo<Candle[] | null>(() => {
    if (!staticData || staticData.length === 0) return null;
    if (range === "MAX") return staticData;
    const last = new Date(staticData[staticData.length - 1].date);
    let cutoff: Date;
    if (range === "YTD") {
      cutoff = new Date(last.getFullYear(), 0, 1);
    } else {
      const years = range === "1Y" ? 1 : range === "3Y" ? 3 : 5;
      cutoff = new Date(last);
      cutoff.setFullYear(cutoff.getFullYear() - years);
    }
    return staticData.filter((p) => new Date(p.date) >= cutoff);
  }, [staticData, range]);

  const {
    data: fetched = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["stockPriceHistory", ticker, period],
    queryFn: () => fetchPriceHistory(ticker, period),
    staleTime: 60 * 60 * 1000,
    retry: 1,
    enabled: !!API_BASE && !filteredStatic,
  });

  const series: Candle[] = filteredStatic ?? fetched;

  const candleSeries = useMemo<CandleWithRange[]>(
    () => series.map((p) => ({ ...p, range: [p.low, p.high] })),
    [series],
  );

  const stats = useMemo(() => {
    if (series.length < 2) return null;
    const first = series[0].close;
    const last = series[series.length - 1].close;
    const change = last - first;
    const pct = (change / first) * 100;
    const min = Math.min(...series.map((p) => p.low ?? p.close));
    const max = Math.max(...series.map((p) => p.high ?? p.close));
    return { first, last, change, pct, min, max };
  }, [series]);

  // Sorted selection (start = earlier date, end = later date) and its delta.
  const selectionStats = useMemo(() => {
    if (!selection) return null;
    const a = selection.start;
    const b = selection.end;
    if (a.date === b.date) return null;
    const [s, e] = a.date < b.date ? [a, b] : [b, a];
    const change = e.close - s.close;
    const pct = (change / s.close) * 100;
    return { start: s, end: e, change, pct, positive: change >= 0 };
  }, [selection]);

  if (!API_BASE && !staticData) {
    return (
      <div className="frame">
        <div className="frame-title">
          <PanelTitle>Price history</PanelTitle>
        </div>
        <p className="px-3 py-3 text-xs text-muted-foreground">
          Live price history requires the local Python backend (yfinance). It is not available on
          the static GitHub Pages build — clone the repo and run the app locally to view this chart.
        </p>
      </div>
    );
  }

  const positive = stats ? stats.change >= 0 : true;
  const lineColor = positive ? UP_COLOR : DOWN_COLOR;

  const headerPositive = positive;
  const yDomain: [number, number] | undefined = stats
    ? [stats.min - (stats.max - stats.min) * 0.05, stats.max + (stats.max - stats.min) * 0.05]
    : undefined;

  const renderTooltip = ({ active, payload }: TooltipContentProps) => {
    if (!active || !payload?.length) return null;
    const p: Partial<Candle> | undefined = payload[0]?.payload;
    if (
      !p ||
      p.date == null ||
      p.close == null ||
      p.open == null ||
      p.high == null ||
      p.low == null
    )
      return null;

    // translateY pulls the tooltip above the cursor; recharts already places it to the right.
    const tooltipClass =
      "rounded-md border border-border bg-popover px-3 py-2 text-xs text-foreground shadow-md tabular-nums";
    const tooltipBox: React.CSSProperties = {
      lineHeight: 1.6,
      transform: "translateY(calc(-100% - 12px))",
    };

    // While dragging, the tooltip reports the selection delta (start → end) instead of the per-candle OHLC.
    if (isDragging && selectionStats) {
      const sel = selectionStats;
      return (
        <div className={tooltipClass} style={tooltipBox}>
          <div style={{ color: "hsl(var(--muted-foreground))" }}>
            {fmtDateFull(sel.start.date)} → {fmtDateFull(sel.end.date)}
          </div>
          <div>
            {`$${sel.start.close.toFixed(2)}`} →{" "}
            <span style={{ fontWeight: 700 }}>{`$${sel.end.close.toFixed(2)}`}</span>
          </div>
          <div style={{ color: sel.positive ? UP_COLOR : DOWN_COLOR, fontWeight: 700 }}>
            {sel.positive ? "+" : ""}
            {sel.change.toFixed(2)} ({sel.positive ? "+" : ""}
            {sel.pct.toFixed(2)}%)
          </div>
        </div>
      );
    }

    const baseline = stats?.first ?? p.close;
    const delta = ((p.close - baseline) / baseline) * 100;
    const isUp = p.close >= p.open;
    return (
      <div className={tooltipClass} style={tooltipBox}>
        <div style={{ color: "hsl(var(--muted-foreground))" }}>{fmtDateFull(p.date)}</div>
        {mode === "candles" ? (
          <div
            style={{ display: "grid", gridTemplateColumns: "auto auto", columnGap: 12, rowGap: 2 }}
          >
            <span style={{ color: "hsl(var(--muted-foreground))" }}>O</span>
            <span>{`$${p.open.toFixed(2)}`}</span>
            <span style={{ color: "hsl(var(--muted-foreground))" }}>H</span>
            <span>{`$${p.high.toFixed(2)}`}</span>
            <span style={{ color: "hsl(var(--muted-foreground))" }}>L</span>
            <span>{`$${p.low.toFixed(2)}`}</span>
            <span style={{ color: "hsl(var(--muted-foreground))" }}>C</span>
            <span style={{ color: isUp ? UP_COLOR : DOWN_COLOR, fontWeight: 700 }}>
              {`$${p.close.toFixed(2)}`}
            </span>
          </div>
        ) : (
          <div style={{ fontWeight: 700 }}>{`$${p.close.toFixed(2)}`}</div>
        )}
        <div style={{ fontSize: 11, color: delta >= 0 ? UP_COLOR : DOWN_COLOR, marginTop: 2 }}>
          {delta >= 0 ? "+" : ""}
          {delta.toFixed(2)}% vs start
        </div>
      </div>
    );
  };

  return (
    <div className="frame">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-3 py-2">
        <div>
          <span className="section-title">Price history</span>
          {stats && (
            <div className="flex items-baseline gap-3 mt-1 flex-wrap">
              <span className="text-xl font-semibold tabular-nums">${stats.last.toFixed(2)}</span>
              <span
                className={`inline-flex items-center gap-1 text-[13px] tabular-nums ${
                  headerPositive ? "delta-positive" : "delta-negative"
                }`}
              >
                {headerPositive ? (
                  <TrendingUp className="h-3.5 w-3.5" />
                ) : (
                  <TrendingDown className="h-3.5 w-3.5" />
                )}
                {headerPositive ? "+" : ""}
                {stats.change.toFixed(2)} ({headerPositive ? "+" : ""}
                {stats.pct.toFixed(2)}%)
              </span>
              <span className="text-xs text-muted-foreground">over {range}</span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <SegmentedControl
            size="sm"
            aria-label="Chart type"
            value={mode}
            onValueChange={(v) => setMode(v)}
            options={[
              {
                value: "candles",
                label: <BarChart3 className="h-3.5 w-3.5" />,
                title: "Candlestick chart",
              },
              { value: "area", label: <Activity className="h-3.5 w-3.5" />, title: "Area chart" },
            ]}
          />
          <SegmentedControl
            size="sm"
            aria-label="Time range"
            value={range}
            onValueChange={(v) => setRange(v)}
            options={RANGES.map((r) => ({
              value: r.key,
              label: <span className="tabular-nums">{r.label}</span>,
            }))}
          />
        </div>
      </div>

      <div className="p-3">
        <div
          ref={containerRef}
          className="h-[320px] w-full cursor-crosshair select-none"
          onDragStart={(e) => e.preventDefault()}
          style={{ touchAction: "none" }}
        >
          {isLoading ? (
            <div className="h-full flex items-center justify-center text-muted-foreground gap-2 text-sm">
              <Loader2 className="h-4 w-4 animate-spin" /> Loading price history…
            </div>
          ) : isError || series.length === 0 ? (
            <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
              Price history unavailable for {ticker}.
            </div>
          ) : !size ? null : mode === "candles" ? (
            <ComposedChart
              width={size.width}
              height={size.height}
              data={candleSeries}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
            >
              <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDateShort}
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
                minTickGap={48}
              />
              <YAxis
                tickFormatter={fmtCurrency}
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
                width={56}
                domain={yDomain ?? ["auto", "auto"]}
              />
              {stats && !selectionStats && (
                <ReferenceLine
                  y={stats.first}
                  stroke={NEUTRAL}
                  strokeDasharray="2 4"
                  strokeOpacity={0.4}
                />
              )}
              {selectionStats && (
                <>
                  <ReferenceArea
                    x1={selectionStats.start.date}
                    x2={selectionStats.end.date}
                    fill={selectionStats.positive ? UP_COLOR : DOWN_COLOR}
                    fillOpacity={0.08}
                  />
                  <ReferenceLine
                    x={selectionStats.start.date}
                    stroke={selectionStats.positive ? UP_COLOR : DOWN_COLOR}
                    strokeDasharray="2 4"
                    strokeOpacity={0.6}
                  />
                  <ReferenceLine
                    x={selectionStats.end.date}
                    stroke={selectionStats.positive ? UP_COLOR : DOWN_COLOR}
                    strokeDasharray="2 4"
                    strokeOpacity={0.6}
                  />
                </>
              )}
              <Tooltip cursor={CURSOR} content={renderTooltip} />
              <Bar
                dataKey="range"
                shape={(props: CandleShapeProps) => <Candlestick {...props} />}
                isAnimationActive={false}
              />
            </ComposedChart>
          ) : (
            <AreaChart
              width={size.width}
              height={size.height}
              data={series}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
            >
              <CartesianGrid stroke={GRID} strokeWidth={1} vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={fmtDateShort}
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
                minTickGap={48}
              />
              <YAxis
                tickFormatter={fmtCurrency}
                tick={AXIS_TICK}
                axisLine={false}
                tickLine={false}
                width={56}
                domain={["auto", "auto"]}
              />
              {stats && !selectionStats && (
                <ReferenceLine
                  y={stats.first}
                  stroke={NEUTRAL}
                  strokeDasharray="2 4"
                  strokeOpacity={0.4}
                />
              )}
              {selectionStats && (
                <>
                  <ReferenceArea
                    x1={selectionStats.start.date}
                    x2={selectionStats.end.date}
                    fill={selectionStats.positive ? UP_COLOR : DOWN_COLOR}
                    fillOpacity={0.12}
                  />
                  <ReferenceLine
                    x={selectionStats.start.date}
                    stroke={selectionStats.positive ? UP_COLOR : DOWN_COLOR}
                    strokeDasharray="2 4"
                    strokeOpacity={0.6}
                  />
                  <ReferenceLine
                    x={selectionStats.end.date}
                    stroke={selectionStats.positive ? UP_COLOR : DOWN_COLOR}
                    strokeDasharray="2 4"
                    strokeOpacity={0.6}
                  />
                </>
              )}
              <Tooltip cursor={CURSOR} content={renderTooltip} />
              <Area
                type="monotone"
                dataKey="close"
                stroke={lineColor}
                strokeWidth={2}
                fill="none"
                dot={false}
                isAnimationActive={chartAnimationActive()}
                animationDuration={400}
              />
            </AreaChart>
          )}
        </div>
      </div>
    </div>
  );
}
