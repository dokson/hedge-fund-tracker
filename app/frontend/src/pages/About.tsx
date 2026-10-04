import { Link } from "react-router";

import { usePageMeta } from "@/hooks/usePageMeta";
import { ABOUT_HEADING, ABOUT_INTRO, ABOUT_SECTIONS, type Segment } from "@/lib/aboutContent";
import { ABOUT_PAGE } from "@/lib/pageMeta";
import { buildBreadcrumbJsonLd, canonicalUrl } from "@/lib/seo";
import { ROUTES } from "@/lib/routes";
import { cn } from "@/lib/utils";

function SegmentText({ segment }: { segment: Segment }) {
  if (typeof segment === "string") return <>{segment}</>;
  if (segment.href.startsWith("/")) {
    return (
      <Link to={segment.href} className="ticker-link">
        {segment.text}
      </Link>
    );
  }
  return (
    <a href={segment.href} target="_blank" rel="noopener noreferrer" className="ticker-link">
      {segment.text}
    </a>
  );
}

/**
 * Who builds the tracker, where its data comes from and what it cannot show.
 * Content lives in aboutContent.ts, shared with the static pre-render.
 */
export default function About() {
  usePageMeta({
    title: ABOUT_PAGE.title,
    description: ABOUT_PAGE.description,
    canonical: canonicalUrl(ABOUT_PAGE.path),
    jsonLd: [
      buildBreadcrumbJsonLd([
        { name: "Home", path: ROUTES.home },
        { name: "About", path: ABOUT_PAGE.path },
      ]),
    ],
  });

  return (
    <div className="max-w-screen-2xl space-y-6">
      <div className="space-y-2">
        <h1 className="page-title">{ABOUT_HEADING}</h1>
        <p className="max-w-[72ch] text-sm text-muted-foreground">{ABOUT_INTRO}</p>
      </div>
      {/* Panels in two columns fill a wide screen while each line stays readable. */}
      <div className="grid gap-4 lg:grid-cols-2">
        {ABOUT_SECTIONS.map((section, index) => (
          <section
            key={section.id}
            id={section.id}
            className={cn(
              "frame scroll-mt-20 space-y-3 p-4",
              // An odd last panel spans both columns so the grid never ends half empty.
              index === ABOUT_SECTIONS.length - 1 &&
                ABOUT_SECTIONS.length % 2 === 1 &&
                "lg:col-span-2",
            )}
          >
            <h2 className="section-title">{section.title}</h2>
            {section.paragraphs.map((segments, i) => (
              <p key={i} className="max-w-[72ch] text-sm leading-6 text-foreground/90">
                {segments.map((segment, j) => (
                  <SegmentText key={j} segment={segment} />
                ))}
              </p>
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
