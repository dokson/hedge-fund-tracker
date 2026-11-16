import { useState } from "react";
import { Info } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * The small "ⓘ" hint icon used next to column headers/labels across the app
 * (Quarterly Trends, AI Ranking, Funds Config, Score tab...) — centralized so
 * the hover target, icon opacity, and tooltip sizing stay consistent instead
 * of being hand-copied per page. It is a button: a keyboard user reaches it and
 * focus shows the hint; a tap opens it too (Radix would otherwise treat the tap
 * as a click that closes it), and Escape or a tap elsewhere dismisses it.
 * `label` names what the hint is about, so a table of ⓘ buttons stays distinguishable.
 */
export function InfoTooltip({
  text,
  label,
  className,
}: {
  text: string;
  label?: string;
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label={label ? `More information: ${label}` : "More information"}
          // Open on activation rather than toggle: hover has usually opened it already.
          onClick={(event) => {
            event.preventDefault();
            setOpen(true);
          }}
          className="-m-1 inline-flex cursor-help items-center justify-center rounded-sm p-1"
        >
          <Info className={cn("h-3 w-3 icon-faint", className)} aria-hidden="true" />
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[280px] text-xs font-normal">
        <p>{text}</p>
      </TooltipContent>
    </Tooltip>
  );
}
