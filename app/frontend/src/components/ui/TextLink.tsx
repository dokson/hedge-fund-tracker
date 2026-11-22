import type { ReactNode } from "react";
import { Link } from "react-router";
import { ArrowUpRight } from "lucide-react";

import { learnItem } from "@/lib/routes";
import { cn } from "@/lib/utils";

// Inside running text the link colour is ~1.1:1 against the body text, so the underline
// must be persistent there (SC 1.4.1); standalone links underline on hover only.
const LINK_CLASS =
  "inline-flex items-center gap-1 text-primary-text underline-offset-4 hover:underline [p_&]:underline";

interface TextLinkBase {
  /** Trailing ↗ marking a jump to another page or site. */
  arrow?: boolean;
  /** Leading icon node (already `aria-hidden`). */
  icon?: ReactNode;
  title?: string;
  className?: string;
  children: ReactNode;
}

/** In-app route (`to`, rendered with the router) or off-site URL (`href`, new tab). */
type TextLinkProps = TextLinkBase & ({ to: string } | { href: string });

/** The one inline text-link style, for in-app routes and external URLs alike. */
export function TextLink(props: TextLinkProps) {
  const { arrow = false, icon, title, className, children } = props;
  const content = (
    <>
      {icon}
      {children}
      {arrow && <ArrowUpRight className="h-3 w-3" aria-hidden="true" />}
    </>
  );
  if ("href" in props) {
    return (
      <a
        href={props.href}
        target="_blank"
        rel="noopener noreferrer"
        title={title}
        className={cn(LINK_CLASS, className)}
      >
        {content}
      </a>
    );
  }
  return (
    <Link to={props.to} title={title} className={cn(LINK_CLASS, className)}>
      {content}
    </Link>
  );
}

/** Link to one FAQ entry; the label defaults to "FAQ". */
export function FaqLink({
  item,
  className,
  children = "FAQ",
}: {
  item: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <TextLink to={learnItem(item)} className={className}>
      {children}
    </TextLink>
  );
}

/** A muted caption line of short facts and links; separate items with `<MetaSep />`. */
export function MetaLine({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <p
      className={cn(
        "flex flex-wrap items-center gap-x-1.5 gap-y-1 text-xs text-muted-foreground",
        className,
      )}
    >
      {children}
    </p>
  );
}

/** The hairline between items of a `MetaLine` or a status line. */
export function MetaSep({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn("inline-block h-3 w-px shrink-0 self-center bg-border", className)}
    />
  );
}
