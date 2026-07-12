import { useEffect, useMemo, useRef, useState } from "react";
import {
  BookOpen,
  CalendarClock,
  ChevronRight,
  FileText,
  Search,
  TriangleAlert,
  Workflow,
  X,
  type LucideIcon,
} from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { usePageMeta } from "@/hooks/usePageMeta";
import { matchesQuery } from "@/lib/utils";
import { type FaqSection, FAQ_LAST_UPDATED, FAQ_META, FAQ_SECTIONS } from "@/lib/faqContent";
import { ROUTES } from "@/lib/routes";
import { buildBreadcrumbJsonLd, buildFaqJsonLd, canonicalUrl } from "@/lib/seo";

/** One icon per section, keyed by `faqContent.ts` section id — presentation-only mapping. */
const SECTION_ICONS: Record<string, LucideIcon> = {
  "sec-filings": FileText,
  "how-it-works": Workflow,
  limitations: TriangleAlert,
};

const LAST_UPDATED_LABEL = new Date(`${FAQ_LAST_UPDATED}T00:00:00Z`).toLocaleDateString("en-US", {
  year: "numeric",
  month: "short",
  day: "numeric",
  timeZone: "UTC",
});

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
  index,
  forceOpen,
  registerRef,
}: {
  section: FaqSection;
  index: number;
  forceOpen: boolean;
  registerRef: (id: string, el: HTMLElement | null) => void;
}) {
  const Icon = SECTION_ICONS[section.id] ?? FileText;
  return (
    <section
      id={section.id}
      ref={(el) => registerRef(section.id, el)}
      className="scroll-mt-20 animate-slide-up"
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: "backwards" }}
    >
      <div className="flex items-baseline gap-3 mb-3">
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary translate-y-0.5">
          <Icon className="h-3.5 w-3.5" />
        </span>
        <h2 className="font-display text-base font-semibold tracking-tight text-foreground">
          {section.title}
        </h2>
        <span className="font-mono text-[11px] text-muted-foreground">
          {section.items.length.toString().padStart(2, "0")}
        </span>
        <span className="h-px flex-1 bg-border/60" aria-hidden="true" />
      </div>
      <div className="surface divide-y divide-border/60 px-5">
        <Accordion
          type="multiple"
          key={forceOpen ? "search" : "browse"}
          defaultValue={forceOpen ? section.items.map((i) => i.id) : []}
        >
          {section.items.map((item, itemIndex) => (
            <AccordionItem key={item.id} value={item.id} id={item.id} className="border-0">
              <AccordionTrigger className="group py-4 text-left hover:no-underline gap-3 [&>svg]:text-muted-foreground">
                <span className="flex items-baseline gap-3 min-w-0">
                  <span className="font-mono text-[11px] text-primary shrink-0 tabular-nums">
                    Q{(itemIndex + 1).toString().padStart(2, "0")}
                  </span>
                  <span className="text-sm text-foreground group-hover:text-primary transition-colors">
                    {item.question}
                  </span>
                </span>
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-3 border-l-2 border-primary/25 pl-[1.9rem] ml-[0.05rem] text-sm leading-relaxed text-muted-foreground">
                  {item.answer.map((paragraph) => (
                    <p key={paragraph}>{paragraph}</p>
                  ))}
                </div>
              </AccordionContent>
            </AccordionItem>
          ))}
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

  const [query, setQuery] = useState("");
  const [activeSection, setActiveSection] = useState(FAQ_SECTIONS[0]?.id);
  const sectionRefs = useRef(new Map<string, HTMLElement>());
  const rootRef = useRef<HTMLDivElement>(null);

  const sections = useMemo(() => filterSections(FAQ_SECTIONS, query), [query]);
  const totalQuestions = useMemo(
    () => FAQ_SECTIONS.reduce((sum, s) => sum + s.items.length, 0),
    [],
  );
  const matchCount = useMemo(
    () => sections.reduce((sum, s) => sum + s.items.length, 0),
    [sections],
  );

  const scrollToSection = (id: string, behavior: ScrollBehavior) => {
    // scrollIntoView's own "smooth" ignores the CSS reduced-motion override
    // above (that only governs browser-native scroll-behavior), so honor the
    // preference explicitly here too.
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    sectionRefs.current
      .get(id)
      ?.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : behavior, block: "start" });
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
    const hashId = window.location.hash.slice(1);
    if (hashId && sectionRefs.current.has(hashId)) {
      scrollToSection(hashId, "auto");
      setActiveSection(hashId);
    } else {
      updateActiveSection();
    }

    scrollParent.addEventListener("scroll", updateActiveSection, { passive: true });
    return () => scrollParent.removeEventListener("scroll", updateActiveSection);
  }, [sections]);

  return (
    // pb-[70vh]: lets any section (including the last one) scroll all the way
    // to the top of the scroll container — without slack after the last
    // section, the browser clamps the scroll offset before it gets there, so
    // the last entries could never become "active" via anchor nav or the rail.
    <div ref={rootRef} className="space-y-8 max-w-screen-2xl pb-[70vh]">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="eyebrow">Knowledge base</span>
          <h1 className="page-title mt-1.5">
            <BookOpen className="page-title-icon" /> {FAQ_META.heading}
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5 max-w-prose">{FAQ_META.intro}</p>
        </div>
        <div className="flex items-center gap-1.5 rounded-md border border-dashed border-border/90 px-2.5 py-1.5 font-mono text-xs font-medium text-foreground/80 shrink-0">
          <CalendarClock className="h-3.5 w-3.5" />
          Reviewed {LAST_UPDATED_LABEL}
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder={`Search ${totalQuestions} questions…`}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="pl-9 pr-9 bg-card border-border"
        />
        {query && (
          <button
            type="button"
            onClick={() => setQuery("")}
            aria-label="Clear search"
            className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded p-1.5 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="grid items-start gap-x-10 gap-y-8 xl:grid-cols-[13rem_minmax(0,1fr)]">
        <nav
          aria-label="FAQ sections"
          className="hidden xl:block sticky top-20 space-y-1 self-start"
        >
          {FAQ_SECTIONS.map((section) => {
            const isActive = activeSection === section.id;
            const isFiltered = !sections.some((s) => s.id === section.id);
            return (
              <a
                key={section.id}
                href={`#${section.id}`}
                onClick={(e) => {
                  e.preventDefault();
                  window.history.replaceState(null, "", `#${section.id}`);
                  scrollToSection(section.id, "smooth");
                  setActiveSection(section.id);
                }}
                aria-current={isActive ? "location" : undefined}
                className={`flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                } ${isFiltered ? "opacity-30 pointer-events-none" : ""}`}
              >
                <ChevronRight
                  className={`h-3 w-3 shrink-0 transition-transform ${isActive ? "translate-x-0.5" : ""}`}
                />
                <span className="truncate">{section.title}</span>
              </a>
            );
          })}
        </nav>

        <div className="min-w-0 space-y-8">
          {query && (
            <p className="text-xs text-muted-foreground">
              {matchCount === 0
                ? `No questions match “${query}”.`
                : `${matchCount} of ${totalQuestions} questions match “${query}”.`}
            </p>
          )}
          {sections.map((section, index) => (
            <FaqSectionBlock
              key={section.id}
              section={section}
              index={index}
              forceOpen={query.trim().length > 0}
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
