import { Gauge } from "lucide-react";
import { Link } from "react-router";

import { SmartScoreBadge } from "@/components/SmartScoreBadge";
import { smartScoreChipClass } from "@/lib/smartScore";
import { stockPath } from "@/lib/routes";
import { cn } from "@/lib/utils";

/**
 * The stock's Smart Score as a header pill, tinted by its bucket. It leads to the
 * score's components on the stock page: an in-page jump there, a link from elsewhere.
 */
export function SmartScorePill({
  score,
  ticker,
  quarterLabel,
  inPage = false,
  className,
}: {
  score: number;
  ticker: string;
  /** The quarter the score ranks against, shown in the hover text. */
  quarterLabel?: string;
  /** On the stock page itself: jump to the Smart Score panel instead of navigating. */
  inPage?: boolean;
  className?: string;
}) {
  const classes = cn(
    smartScoreChipClass(score),
    "h-8 gap-1.5 px-3 text-sm font-semibold no-underline hover:underline underline-offset-2",
    className,
  );
  const title = `Smart Score${quarterLabel ? ` ${quarterLabel.replace("Q", " Q")}` : ""}: relative institutional screen (1–10), not a return forecast. Open its components.`;
  const content = (
    <>
      <Gauge className="h-4 w-4" aria-hidden="true" />
      <span className="text-foreground max-sm:sr-only">Smart Score</span>
      <SmartScoreBadge score={score} title="" />
    </>
  );
  return inPage ? (
    <a href="#smart-score" className={classes} title={title}>
      {content}
    </a>
  ) : (
    <Link to={stockPath(ticker)} className={classes} title={title}>
      {content}
    </Link>
  );
}
