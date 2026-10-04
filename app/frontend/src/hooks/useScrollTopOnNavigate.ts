import { useEffect, useRef } from "react";
import { useLocation } from "react-router";

/**
 * Start each new screen at the top. Phones scroll the document rather than a
 * remounted container, so the previous page's offset would otherwise carry over.
 * A hash target is left to the page that owns it.
 */
export function useScrollTopOnNavigate(): void {
  const { pathname, hash } = useLocation();
  const previousPath = useRef(pathname);

  useEffect(() => {
    // A hash change alone scrolls within the same screen.
    if (previousPath.current === pathname) return;
    previousPath.current = pathname;
    if (!hash) window.scrollTo(0, 0);
  }, [pathname, hash]);
}
