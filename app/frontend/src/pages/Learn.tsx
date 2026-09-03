import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router";
import { Search, X } from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { usePageMeta } from "@/hooks/usePageMeta";
import { matchesQuery } from "@/lib/utils";
import {
  type FaqItem,
  type FaqSection,
  FAQ_LAST_UPDATED,
  FAQ_META,
  FAQ_SECTIONS,
} from "@/lib/faqContent";
import { ROUTES } from "@/lib/routes";
import { buildBreadcrumbJsonLd, buildFaqJsonLd, canonicalUrl } from "@/lib/seo";

const LAST_UPDATED_LABEL = new Date(`${FAQ_LAST_UPDATED}T00:00:00Z`).toLocaleDateString("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

// Questions are numbered once, across every section, so "Q07" names the same
// entry whether or not a search filter is hiding its neighbours.
const QUESTION_NUMBERS = new Map<string, number>(
  FAQ_SECTIONS.flatMap((s) => s.items).map((item, i) => [item.id, i + 1]),
);

/** Every question, by id — used to resolve a `/learn#<item-id>` deep link. */
const ITEMS_BY_ID = new Map<string, FaqItem>(
  FAQ_SECTIONS.flatMap((s) => s.items).map((item) => [item.id, item]),
);

/**
 * Walks up from `node` to find the nearest scrollable ancestor. The app shell
 * (`DashboardLayout`) scrolls inside `<main class="overflow-auto">`, not the
 * window/document, so neither native hash-scroll-on-load nor a
 * viewport-rooted IntersectionObserver can be relied on here.
 */
function getScrollParent(node: HTMLElement | null): HTMLElement | null {
  let el = node?.parentElement ?? null;
  while (el) {
    if (/(auto|scroll)/.test(getComputedStyle(el).overflowY)) return el;
    el = el.parentElement;
  }
  return null;
}

/** `matchMedia` is absent in some non-browser environments (jsdom), so guard it. */
function prefersReducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/**
 * The search box's value together with the URL hash it was typed under. Storing
 * the pair is what lets a later hash change drop a filter hiding its target
 * without an effect writing back into state.
 */
type TypedQuery = {
  readonly hash: string | null;
  readonly value: string;
};

/**
 * Accordion items opened by hand, valid only for the query/hash basis they were
 * toggled under; any change to that basis falls back to the derived open set.
 */
type ManualOpen = {
  readonly basis: string;
  readonly items: readonly string[];
};

/**
 * The URL hash wins over the search box: navigating to a question the current
 * filter would hide clears the filter rather than showing an empty page.
 */
function clearFilterHiding(query: string, hashItemId: string | null): string {
  if (!query.trim() || !hashItemId) return query;
  const item = ITEMS_BY_ID.get(hashItemId);
  return item && !matchesQuery(query, item.question, ...item.answer) ? "" : query;
}

function filterSections(sections: FaqSection[], query: string): FaqSection[] {
  if (!query.trim()) return sections;
  return sections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => matchesQuery(query, item.question, ...item.answer)),
    }))
    .filter((section) => section.items.length > 0);
}

function FaqSectionBlock({
  section,
  open,
  onOpenChange,
  registerRef,
}: {
  section: FaqSection;
  /** Ids of this section's open items (the accordion is fully controlled). */
  open: string[];
  onOpenChange: (sectionItemIds: string[], next: string[]) => void;
  registerRef: (id: string, el: HTMLElement | null) => void;
}) {
  const itemIds = section.items.map((i) => i.id);
  return (
    <section id={section.id} ref={(el) => registerRef(section.id, el)} className="scroll-mt-20">
      <div className="flex items-baseline gap-3 mb-3">
        <h2 className="section-title">{section.title}</h2>
        <span className="text-xs text-muted-foreground tabular-nums">{section.items.length}</span>
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
      </div>
      <div className="frame px-3">
        <Accordion
          type="multiple"
          value={open}
          onValueChange={(next) => onOpenChange(itemIds, next)}
        >
          {section.items.map((item) => {
            const n = QUESTION_NUMBERS.get(item.id) ?? 0;
            return (
              <AccordionItem
                key={item.id}
                value={item.id}
                className="border-b border-border/60 last:border-0"
              >
                {/* The id lives on the trigger so `/learn#<id>` lands on a
                    focusable element, and so it matches the anchor the static
                    pre-render emits (renderFaqStaticHtml in lib/seo.ts). */}
                <AccordionTrigger
                  id={item.id}
                  className="scroll-mt-20 py-3 text-left font-normal hover:no-underline gap-3 [&>svg]:text-muted-foreground"
                >
                  <span className="flex items-baseline gap-3 min-w-0">
                    <span
                      className="text-xs text-muted-foreground shrink-0 tabular-nums"
                      aria-hidden="true"
                    >
                      Q{n.toString().padStart(2, "0")}
                    </span>
                    <span className="sr-only">Question {n}</span>
                    <span className="text-[13px] text-foreground">{item.question}</span>
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-3 border-l border-border pl-4 ml-[1.5ch] text-sm leading-6 text-muted-foreground">
                    {item.answer.map((paragraph) => (
                      <p key={paragraph}>{paragraph}</p>
                    ))}
                  </div>
                </AccordionContent>
              </AccordionItem>
            );
          })}
        </Accordion>
      </div>
    </section>
  );
}

export default function Learn() {
  const jsonLd = useMemo(
    () => [
      buildFaqJsonLd(FAQ_SECTIONS),
      // Breadcrumb is emitted as structured data only (no visible breadcrumb UI).
      buildBreadcrumbJsonLd([
        { name: "Home", path: ROUTES.home },
        { name: "FAQ", path: ROUTES.learn },
      ]),
    ],
    [],
  );

  usePageMeta({
    title: FAQ_META.title,
    description: FAQ_META.description,
    canonical: canonicalUrl(ROUTES.learn),
    jsonLd,
  });

  const [typedQuery, setTypedQuery] = useState<TypedQuery>({ hash: null, value: "" });
  const [manualOpen, setManualOpen] = useState<ManualOpen | null>(null);
  const [activeSection, setActiveSection] = useState(FAQ_SECTIONS[0]?.id);
  const sectionRefs = useRef(new Map<string, HTMLElement>());
  const rootRef = useRef<HTMLDivElement>(null);

  // A `/learn#<item-id>` deep link (see `learnItem()` in lib/routes.ts). Read
  // from the router so it also reacts to hash changes while already on /learn.
  const { hash } = useLocation();
  const hashItemId = useMemo(() => {
    const id = decodeURIComponent(hash.replace(/^#/, ""));
    return ITEMS_BY_ID.has(id) ? id : null;
  }, [hash]);

  const query =
    typedQuery.hash === hashItemId
      ? typedQuery.value
      : clearFilterHiding(typedQuery.value, hashItemId);
  const setQuery = (value: string) => setTypedQuery({ hash: hashItemId, value });

  const sections = useMemo(() => filterSections(FAQ_SECTIONS, query), [query]);
  const totalQuestions = QUESTION_NUMBERS.size;
  const matchCount = useMemo(
    () => sections.reduce((sum, s) => sum + s.items.length, 0),
    [sections],
  );

  // A search expands every match (the answers are what is being searched), no
  // search leaves only the hash-pinned question open. Derived during render
  // rather than synchronised by an effect, so the deep-linked item is already
  // expanded in the first commit.
  const openBasis = JSON.stringify([query.trim(), hashItemId]);
  const openItems = useMemo<readonly string[]>(() => {
    if (manualOpen?.basis === openBasis) return manualOpen.items;
    if (query.trim()) return sections.flatMap((s) => s.items.map((i) => i.id));
    return hashItemId ? [hashItemId] : [];
  }, [manualOpen, openBasis, query, sections, hashItemId]);

  // Scrolling and focus are the one genuinely external thing a deep link does,
  // so they stay in an effect — keyed on the hash, which is what changed.
  useEffect(() => {
    if (!hashItemId) return;
    let cancelled = false;
    let frame = 0;
    let attempts = 0;

    const scrollTo = (trigger: HTMLElement, behavior: ScrollBehavior) => {
      trigger.scrollIntoView?.({ behavior, block: "start" });
    };

    // On a cold load the accordion content is still mounting and the web font
    // has not swapped in yet, so a single smooth scroll issued in the same tick
    // as the open state either resolves against a stale layout or is cancelled
    // outright and the viewport never moves. So: wait for the trigger and for a
    // painted frame, scroll, then correct once layout has settled.
    const run = () => {
      if (cancelled) return;
      const trigger = document.getElementById(hashItemId);
      if (!trigger) {
        if (attempts++ > 30) return;
        frame = requestAnimationFrame(run);
        return;
      }
      const reduced = prefersReducedMotion();
      scrollTo(trigger, reduced ? "auto" : "smooth");
      // preventScroll: focus()'s own scrolling would fight the one above.
      trigger.focus({ preventScroll: true });

      const settle = () => {
        if (cancelled) return;
        const el = document.getElementById(hashItemId);
        if (!el) return;
        const target = parseFloat(getComputedStyle(el).scrollMarginTop) || 0;
        const parentTop = getScrollParent(el)?.getBoundingClientRect().top ?? 0;
        if (Math.abs(el.getBoundingClientRect().top - (parentTop + target)) > 4) {
          scrollTo(el, "auto");
        }
      };
      void (document.fonts?.ready ?? Promise.resolve()).then(() => {
        if (cancelled) return;
        frame = requestAnimationFrame(() => {
          frame = requestAnimationFrame(settle);
        });
      });
    };

    // A double rAF: the first frame commits the open item's layout, the second
    // runs after it has been measured.
    frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(run);
    });
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [hashItemId]);

  const scrollToSection = (id: string, behavior: ScrollBehavior) => {
    // scrollIntoView's own "smooth" ignores the CSS reduced-motion override
    // above (that only governs browser-native scroll-behavior), so honor the
    // preference explicitly here too.
    sectionRefs.current
      .get(id)
      ?.scrollIntoView?.({ behavior: prefersReducedMotion() ? "auto" : behavior, block: "start" });
  };

  // Scroll-spy: highlight the index-rail entry for whichever section heading
  // is currently nearest the top of the scroll container. The app shell
  // scrolls inside <main>, not the window, so this tracks that container's
  // own scroll position directly instead of using a viewport-rooted
  // IntersectionObserver (which never fires for a nested scroll container).
  useEffect(() => {
    const scrollParent = getScrollParent(rootRef.current);
    if (!scrollParent) return;

    const updateActiveSection = () => {
      const containerTop = scrollParent.getBoundingClientRect().top;
      const threshold = containerTop + 96; // roughly the sticky header height
      let current = FAQ_SECTIONS[0]?.id;
      for (const section of sections) {
        const el = sectionRefs.current.get(section.id);
        if (el && el.getBoundingClientRect().top <= threshold) current = section.id;
      }
      if (current) setActiveSection(current);
    };

    // Deep-link support: jump straight to the section named in the URL hash
    // on first load (the browser's native hash-scroll only targets the
    // window, so it never reaches content inside a nested scroll container).
    const hashId = decodeURIComponent(hash.replace(/^#/, ""));
    if (!hashItemId && hashId && sectionRefs.current.has(hashId)) {
      scrollToSection(hashId, "auto");
      setActiveSection(hashId);
    } else {
      updateActiveSection();
    }

    scrollParent.addEventListener("scroll", updateActiveSection, { passive: true });
    return () => scrollParent.removeEventListener("scroll", updateActiveSection);
  }, [sections, hash, hashItemId]);

  return (
    // pb-[70vh]: lets any section (including the last one) scroll all the way
    // to the top of the scroll container — without slack after the last
    // section, the browser clamps the scroll offset before it gets there, so
    // the last entries could never become "active" via anchor nav or the rail.
    <div ref={rootRef} className="space-y-8 max-w-screen-2xl pb-[70vh]">
      <div className="space-y-2">
        <h1 className="page-title">{FAQ_META.heading}</h1>
        <p className="text-sm text-muted-foreground max-w-[64ch]">{FAQ_META.intro}</p>
        <p className="status-line text-muted-foreground">
          Board info <span aria-hidden="true">·</span> Reviewed {LAST_UPDATED_LABEL}{" "}
          <span aria-hidden="true">·</span> Questions {totalQuestions}
        </p>
      </div>

      <div className="relative max-w-md">
        <Search
          className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none"
          aria-hidden="true"
        />
        <Input
          placeholder={`Search ${totalQuestions} questions…`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search questions"
          className="pl-8 pr-9"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Clear search"
            className="absolute right-0 top-0 h-9 w-9 flex items-center justify-center text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="grid items-start gap-x-10 gap-y-8 xl:grid-cols-[16rem_minmax(0,1fr)]">
        <nav aria-label="FAQ sections" className="hidden xl:block sticky top-20 self-start">
          <ol>
            {FAQ_SECTIONS.map((section) => {
              const isActive = activeSection === section.id;
              const isFiltered = !sections.some((s) => s.id === section.id);
              return (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    onClick={(e) => {
                      e.preventDefault();
                      window.history.replaceState(null, "", `#${section.id}`);
                      scrollToSection(section.id, "smooth");
                      setActiveSection(section.id);
                    }}
                    aria-current={isActive ? "location" : undefined}
                    data-active={isActive || undefined}
                    className={`menu-line ${isFiltered ? "opacity-30 pointer-events-none" : ""}`}
                  >
                    <span className="truncate">{section.title}</span>
                    <span className="tabular-nums">{section.items.length}</span>
                  </a>
                </li>
              );
            })}
          </ol>
        </nav>

        <div className="min-w-0 space-y-8">
          {query && (
            <p className="text-xs text-muted-foreground" role="status">
              {matchCount === 0
                ? `No questions match “${query}”.`
                : `${matchCount} of ${totalQuestions} questions match “${query}”.`}
            </p>
          )}
          {sections.map((section) => (
            <FaqSectionBlock
              key={section.id}
              section={section}
              open={openItems.filter((id) => section.items.some((i) => i.id === id))}
              onOpenChange={(sectionItemIds, next) =>
                setManualOpen({
                  basis: openBasis,
                  items: [...openItems.filter((id) => !sectionItemIds.includes(id)), ...next],
                })
              }
              registerRef={(id, el) => {
                if (el) sectionRefs.current.set(id, el);
                else sectionRefs.current.delete(id);
              }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
