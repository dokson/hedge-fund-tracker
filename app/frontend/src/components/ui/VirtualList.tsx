import { useCallback, useContext, useLayoutEffect, useRef, type ReactNode } from "react";
import { useLocation, useNavigationType } from "react-router";
import { useVirtualizer, type VirtualItem } from "@tanstack/react-virtual";

import { ResearchContext } from "@/hooks/useResearchState";

interface VirtualListProps<T> {
  /** Full list to window — only the visible slice is mounted. */
  items: T[];
  /** Estimated row height in px (used before measurement; rows may vary). */
  estimateSize: number;
  /** Stable key per item. */
  getKey: (item: T, index: number) => string | number;
  /** Renders a single row's content. */
  renderItem: (item: T, index: number) => ReactNode;
  /** Classes for the scroll container — set a height/max-height here. */
  className?: string;
  /** Extra rows rendered above/below the viewport to smooth fast scrolls. */
  overscan?: number;
  /** Stable viewport identity for per-history-entry research scroll restoration. */
  scrollKey?: string;
}

interface VirtualScrollMemory {
  values: Map<string, unknown>;
  key: string;
  restore: boolean;
}

interface VirtualScrollSnapshot {
  offset: number;
  measurements: VirtualItem[];
}

function ResearchVirtualList<T>(props: VirtualListProps<T> & { scrollKey: string }) {
  const memory = useContext(ResearchContext);
  const { key, hash } = useLocation();
  const navigationType = useNavigationType();
  if (!memory) throw new Error("Research virtual scrolling requires a ResearchProvider");
  return (
    <VirtualListViewport
      {...props}
      memory={{
        values: memory.values,
        key: `\0research-virtual\0${key}\0${props.scrollKey}`,
        restore: navigationType === "POP" && !hash,
      }}
    />
  );
}

/**
 * Windowed vertical list: mounts only the rows in (and near) the viewport, so
 * a 1,000-row list costs the DOM of a dozen. Row height is measured per row
 * via `measureElement`, so variable-height content works without a fixed size.
 *
 * Layout is a sized spacer with absolutely-positioned rows (translateY); the
 * caller owns the scroll container's height through `className`. Headers stay
 * outside this component so they don't scroll with the body.
 */
export function VirtualList<T>(props: VirtualListProps<T>) {
  return props.scrollKey === undefined
    ? <VirtualListViewport {...props} />
    : <ResearchVirtualList {...props} scrollKey={props.scrollKey} />;
}

function VirtualListViewport<T>({
  items,
  estimateSize,
  getKey,
  renderItem,
  className,
  overscan = 8,
  scrollKey,
  memory,
}: VirtualListProps<T> & { memory?: VirtualScrollMemory }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const initial = useRef(memory?.restore
    ? memory.values.get(memory.key) as VirtualScrollSnapshot | undefined
    : undefined).current;
  const values = memory?.values;
  const storageKey = memory?.key;
  const getItemKey = useCallback((index: number) => getKey(items[index], index), [getKey, items]);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    getItemKey,
    initialOffset: initial?.offset,
    initialMeasurementsCache: initial?.measurements,
    overscan,
  });

  useLayoutEffect(() => () => {
    if (values && storageKey !== undefined) {
      values.set(storageKey, {
        offset: virtualizer.scrollOffset ?? 0,
        measurements: virtualizer.takeSnapshot(),
      } satisfies VirtualScrollSnapshot);
    }
  }, [storageKey, values, virtualizer]);

  return (
    <div ref={parentRef} data-research-scroll={scrollKey} className={className} style={{ overflow: "auto" }}>
      <div style={{ height: virtualizer.getTotalSize(), position: "relative", width: "100%" }}>
        {virtualizer.getVirtualItems().map((virtualRow) => {
          const item = items[virtualRow.index];
          return (
            <div
              key={getKey(item, virtualRow.index)}
              data-index={virtualRow.index}
              ref={virtualizer.measureElement}
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: "100%",
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              {renderItem(item, virtualRow.index)}
            </div>
          );
        })}
      </div>
    </div>
  );
}
