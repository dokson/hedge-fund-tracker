import { useRef, type ReactNode } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

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
export function VirtualList<T>({
  items,
  estimateSize,
  getKey,
  renderItem,
  className,
  overscan = 8,
}: VirtualListProps<T>) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: items.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimateSize,
    overscan,
  });

  return (
    <div ref={parentRef} className={className} style={{ overflow: "auto" }}>
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
