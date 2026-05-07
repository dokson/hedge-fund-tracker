import type { ReactNode } from "react";
import { useElementSize } from "@/hooks/useElementSize";

/**
 * Drop-in replacement for Recharts' ResponsiveContainer that defers mounting
 * the chart until its container has real pixel dimensions. Avoids the
 * "width(-1) and height(-1)" warning emitted by ResponsiveContainer during
 * its initial mount before ResizeObserver has fired.
 *
 * The child is a render-prop receiving the measured `{ width, height }`.
 */
export function MeasuredChart({
  className = "",
  children,
}: {
  className?: string;
  children: (size: { width: number; height: number }) => ReactNode;
}) {
  const [ref, size] = useElementSize();
  return (
    <div ref={ref} className={`w-full h-full ${className}`}>
      {size ? children(size) : null}
    </div>
  );
}
