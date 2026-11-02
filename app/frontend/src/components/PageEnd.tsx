import { ArrowUp } from "lucide-react";

import { TextLink } from "@/components/ui/TextLink";

interface PageEndProps {
  /** Where to go next, in order. */
  links: readonly { label: string; to: string }[];
}

/** Desktop scrolls `main`, phones scroll the document: reset whichever moved. */
function scrollToTop() {
  const main = document.getElementById("main");
  if (main) main.scrollTop = 0;
  if (document.scrollingElement) document.scrollingElement.scrollTop = 0;
}

/**
 * The end of a long page: where to go next, and a way back to the top.
 */
export function PageEnd({ links }: PageEndProps) {
  return (
    <nav
      aria-label="Keep exploring"
      className="flex flex-wrap items-center gap-x-5 gap-y-1 border-t border-border pt-3 text-sm"
    >
      {links.map((link) => (
        <TextLink key={link.to} to={link.to} className="min-h-9">
          {link.label}
        </TextLink>
      ))}
      <button
        type="button"
        onClick={scrollToTop}
        className="ml-auto inline-flex min-h-9 items-center gap-1 text-muted-foreground hover:text-foreground"
      >
        <ArrowUp className="h-3.5 w-3.5" aria-hidden="true" />
        Back to top
      </button>
    </nav>
  );
}
