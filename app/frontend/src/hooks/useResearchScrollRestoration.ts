import { useContext, useLayoutEffect, useRef, type RefObject } from "react";
import { useLocation, useNavigationType } from "react-router";

import { ResearchContext } from "./useResearchState";

interface Offset {
  x: number;
  y: number;
}

interface ScrollEntry {
  window: Offset;
  main: Offset;
  nested: Record<string, Offset>;
}

const entryKey = (key: string) => `\0research-scroll\0${key}`;
const readElement = (element: HTMLElement): Offset => ({
  x: element.scrollLeft,
  y: element.scrollTop,
});
const readWindow = (): Offset => ({ x: window.scrollX, y: window.scrollY });
const scrollingKeys: Record<string, true> = {
  ArrowUp: true,
  ArrowDown: true,
  ArrowLeft: true,
  ArrowRight: true,
  PageUp: true,
  PageDown: true,
  Home: true,
  End: true,
  " ": true,
};

/** Restores history entries once their scrollable content is ready, without retaining page data. */
export function useResearchScrollRestoration(mainRef: RefObject<HTMLElement | null>): void {
  const memory = useContext(ResearchContext);
  if (!memory) throw new Error("Research scroll restoration requires a ResearchProvider");
  const values = memory.values;
  const { key, pathname, hash } = useLocation();
  const navigationType = useNavigationType();
  const previousPath = useRef(pathname);

  useLayoutEffect(() => {
    const previous = window.history.scrollRestoration;
    window.history.scrollRestoration = "manual";
    return () => {
      window.history.scrollRestoration = previous;
    };
  }, []);

  useLayoutEffect(() => {
    const main = mainRef.current;
    if (!main) return;
    const pathChanged = previousPath.current !== pathname;
    previousPath.current = pathname;
    const stored = values.get(entryKey(key)) as ScrollEntry | undefined;
    const restore = navigationType === "POP" && stored !== undefined && !hash;
    const entry: ScrollEntry = restore
      ? { window: stored.window, main: stored.main, nested: { ...stored.nested } }
      : { window: readWindow(), main: readElement(main), nested: {} };
    const pending = new Map<string, Offset>();
    if (restore) {
      pending.set("window", entry.window);
      pending.set("main", entry.main);
      for (const [name, offset] of Object.entries(entry.nested))
        pending.set(`nested:${name}`, offset);
    } else if (pathChanged && !hash) {
      if (window.scrollX || window.scrollY) window.scrollTo(0, 0);
      main.scrollLeft = 0;
      main.scrollTop = 0;
    }
    values.set(entryKey(key), entry);

    const viewports = () =>
      Array.from(main.querySelectorAll<HTMLElement>("[data-research-scroll]"));
    const save = () => {
      if (!pending.has("window")) entry.window = readWindow();
      if (!pending.has("main")) entry.main = readElement(main);
      for (const element of viewports()) {
        const name = element.dataset.researchScroll!;
        // Hidden responsive variants must not replace their last visible offset with zero.
        if (!pending.has(`nested:${name}`) && (element.clientHeight || element.clientWidth)) {
          entry.nested[name] = readElement(element);
        }
      }
    };
    save();
    window.addEventListener("scroll", save, true);
    window.addEventListener("pagehide", save);
    window.addEventListener("click", save, true);
    window.addEventListener("popstate", save);

    let resizeObserver: ResizeObserver | undefined;
    let mutationObserver: MutationObserver | undefined;
    let frame: number | undefined;
    let deadline: number | undefined;
    const observed = new Set<Element>();
    const stopRestoring = () => {
      resizeObserver?.disconnect();
      mutationObserver?.disconnect();
      if (frame !== undefined) cancelAnimationFrame(frame);
      frame = undefined;
      if (deadline !== undefined) window.clearTimeout(deadline);
      deadline = undefined;
      window.removeEventListener("wheel", cancel, true);
      window.removeEventListener("touchmove", cancel, true);
      window.removeEventListener("pointerdown", cancel, true);
      window.removeEventListener("keydown", onKeyDown, true);
    };
    const cancel = () => {
      pending.clear();
      stopRestoring();
      save();
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (Object.hasOwn(scrollingKeys, event.key)) cancel();
    };
    const observeContent = () => {
      if (!resizeObserver) return;
      const elements = new Set<Element>([
        document.documentElement,
        document.body,
        main,
        ...main.children,
      ]);
      for (const element of viewports()) {
        elements.add(element);
        if (element.firstElementChild) elements.add(element.firstElementChild);
      }
      for (const element of observed) {
        if (!elements.has(element)) {
          resizeObserver.unobserve(element);
          observed.delete(element);
        }
      }
      for (const element of elements) {
        if (!observed.has(element)) {
          resizeObserver.observe(element);
          observed.add(element);
        }
      }
    };
    const apply = () => {
      const nested = new Map(
        viewports().map((element) => [`nested:${element.dataset.researchScroll}`, element]),
      );
      for (const [target, offset] of pending) {
        const element =
          target === "window"
            ? (document.scrollingElement as HTMLElement | null)
            : target === "main"
              ? main
              : nested.get(target);
        if (!element) continue;
        // A viewport hidden at this breakpoint cannot take its saved offset.
        if (target.startsWith("nested:") && !element.clientHeight && !element.clientWidth) {
          pending.delete(target);
          continue;
        }
        const maxX = Math.max(0, element.scrollWidth - element.clientWidth);
        const maxY = Math.max(0, element.scrollHeight - element.clientHeight);
        // Never let a loading shell clamp a deep saved position to zero.
        if (maxX + 1 < offset.x || maxY + 1 < offset.y) continue;
        const current = target === "window" ? readWindow() : readElement(element);
        if (Math.abs(current.x - offset.x) > 1 || Math.abs(current.y - offset.y) > 1) {
          if (target === "window") window.scrollTo(offset.x, offset.y);
          else {
            element.scrollLeft = offset.x;
            element.scrollTop = offset.y;
          }
        }
        const applied = target === "window" ? readWindow() : readElement(element);
        if (Math.abs(applied.x - offset.x) <= 1 && Math.abs(applied.y - offset.y) <= 1)
          pending.delete(target);
      }
      save();
      if (pending.size === 0) stopRestoring();
    };
    const schedule = () => {
      if (frame !== undefined) return;
      frame = requestAnimationFrame(() => {
        frame = undefined;
        observeContent();
        apply();
      });
    };

    if (pending.size > 0) {
      window.addEventListener("wheel", cancel, { capture: true, passive: true });
      window.addEventListener("touchmove", cancel, { capture: true, passive: true });
      window.addEventListener("pointerdown", cancel, true);
      window.addEventListener("keydown", onKeyDown, true);
      resizeObserver = new ResizeObserver(schedule);
      mutationObserver = new MutationObserver(schedule);
      mutationObserver.observe(main, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ["style", "class"],
      });
      observeContent();
      // Content that never grows back (filters changed, data failed) must not pin the page.
      deadline = window.setTimeout(cancel, 5000);
      apply();
    }

    return () => {
      stopRestoring();
      window.removeEventListener("scroll", save, true);
      window.removeEventListener("pagehide", save);
      window.removeEventListener("click", save, true);
      window.removeEventListener("popstate", save);
      // Scroll events saved the outgoing DOM before React replaced it. Reading it
      // here could overwrite the entry with a detached node's clamped position.
    };
  }, [hash, key, mainRef, navigationType, pathname, values]);
}
