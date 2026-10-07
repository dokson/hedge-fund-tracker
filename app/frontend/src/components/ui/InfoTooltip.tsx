import { Info } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * The small "ⓘ" hint icon used next to column headers/labels across the app
 * (Quarterly Trends, AI Ranking, Funds Config, Score tab...) — centralized so
 * the hover target, icon opacity, and tooltip sizing stay consistent instead
 * of being hand-copied per page. It is a button, so a keyboard user can reach
 * it and a tap on a touch screen focuses it, which is what opens the hint.
 */
export function InfoTooltip({ text, className }: { text: string; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-label="More information"
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
