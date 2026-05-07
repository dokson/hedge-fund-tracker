import { useEffect, useRef, useState } from "react";

/**
 * Tracks the rendered size of a DOM element via ResizeObserver.
 *
 * Returns `[ref, size]` where `size` is `null` until the first measurement.
 * Use this to mount layout-sensitive children (e.g. Recharts charts) only
 * once their container has real pixel dimensions, avoiding the
 * "width(-1) and height(-1)" warning that ResponsiveContainer emits during
 * its initial mount.
 */
export function useElementSize<T extends HTMLElement = HTMLDivElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState<{ width: number; height: number } | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const cr = entries[0]?.contentRect;
      if (cr && cr.width > 0 && cr.height > 0) {
        setSize((prev) =>
          prev && prev.width === cr.width && prev.height === cr.height
            ? prev
            : { width: cr.width, height: cr.height }
        );
      }
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return [ref, size] as const;
}
