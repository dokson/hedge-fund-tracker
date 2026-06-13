import { useMemo } from "react";
import { BookOpen } from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { usePageMeta } from "@/hooks/usePageMeta";
import { type FaqSection, FAQ_META, FAQ_SECTIONS } from "@/lib/faqContent";
import { ROUTES } from "@/lib/routes";
import { buildBreadcrumbJsonLd, buildFaqJsonLd, canonicalUrl } from "@/lib/seo";

/** Approximate rendered height of a section, in "rows" (heading + items). */
const sectionWeight = (section: FaqSection) => section.items.length + 1;

/**
 * Splits sections into two independent columns at the contiguous break point
 * that best balances their total weight. Contiguous (prefix/suffix) keeps the
 * reading order intact when the columns stack into one on narrow screens, while
 * independent containers mean expanding an answer in one column never shifts
 * the other.
 */
function splitIntoColumns(sections: FaqSection[]): [FaqSection[], FaqSection[]] {
  const total = sections.reduce((sum, s) => sum + sectionWeight(s), 0);
  let acc = 0;
  let splitAt = sections.length;
  let best = Infinity;
  for (let i = 1; i < sections.length; i += 1) {
    acc += sectionWeight(sections[i - 1]);
    const diff = Math.abs(acc - (total - acc));
    if (diff < best) {
      best = diff;
      splitAt = i;
    }
  }
  return [sections.slice(0, splitAt), sections.slice(splitAt)];
}

function FaqSectionBlock({ section }: { section: FaqSection }) {
  return (
    <section id={section.id} className="scroll-mt-6 space-y-3">
      <div className="flex items-center gap-3">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-foreground/80">
          {section.title}
        </h2>
        <span className="h-px flex-1 bg-border/60" aria-hidden="true" />
      </div>
      <div className="surface px-5">
        <Accordion type="multiple">
          {section.items.map((item) => (
            <AccordionItem key={item.id} value={item.id} id={item.id} className="last:border-0">
              <AccordionTrigger className="text-left text-sm text-foreground hover:no-underline">
                {item.question}
              </AccordionTrigger>
              <AccordionContent>
                <div className="space-y-3 pr-4 text-sm leading-relaxed text-muted-foreground">
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

  const columns = useMemo(() => splitIntoColumns(FAQ_SECTIONS), []);

  return (
    <div className="space-y-8 max-w-screen-2xl">
      <div>
        <span className="eyebrow">Knowledge base</span>
        <h1 className="page-title mt-1.5">
          <BookOpen className="page-title-icon" /> {FAQ_META.heading}
        </h1>
        <p className="text-sm text-muted-foreground mt-1.5 max-w-prose">{FAQ_META.intro}</p>
      </div>

      {/* Two independent columns: each stacks its own sections, so expanding an
          answer in one column doesn't push the other. Collapses to one on < lg. */}
      <div className="grid items-start gap-x-8 gap-y-8 lg:grid-cols-2">
        {columns.map((column) => (
          <div key={column.map((s) => s.id).join("-")} className="min-w-0 space-y-8">
            {column.map((section) => (
              <FaqSectionBlock key={section.id} section={section} />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
