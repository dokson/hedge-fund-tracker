import { Fragment } from "react";
import { ChevronRight } from "lucide-react";
import { Link } from "react-router";

interface BreadcrumbProps {
  /** The ancestors, outermost first. */
  trail: readonly { label: string; to: string }[];
  /** The page itself: not a link. */
  current: string;
}

/**
 * Where this page sits: links to its ancestors, then the page itself.
 */
export function Breadcrumb({ trail, current }: BreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
        {trail.map((step) => (
          <Fragment key={step.to}>
            <li>
              <Link
                to={step.to}
                className="inline-flex min-h-6 items-center rounded-sm hover:text-foreground hover:underline"
              >
                {step.label}
              </Link>
            </li>
            <li aria-hidden="true">
              <ChevronRight className="h-3 w-3" />
            </li>
          </Fragment>
        ))}
        <li aria-current="page" className="min-w-0 truncate font-medium text-foreground">
          {current}
        </li>
      </ol>
    </nav>
  );
}
