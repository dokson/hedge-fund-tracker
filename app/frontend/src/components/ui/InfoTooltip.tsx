import { Info } from "lucide-react";

import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

/**
 * The small "ⓘ" hint icon used next to column headers/labels across the app
 * (Quarterly Trends, AI Ranking, Funds Config, Score tab...) — centralized so
 * the hover target, icon opacity, and tooltip sizing stay consistent instead
 * of being hand-copied per page.
 */
export function InfoTooltip({ text, className }: { text: string; className?: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info className={cn("h-3 w-3 icon-faint cursor-help", className)} />
      </TooltipTrigger>
      <TooltipContent
        side="top"
        className="max-w-[280px] text-xs font-normal normal-case tracking-normal"
      >
        <p>{text}</p>
      </TooltipContent>
    </Tooltip>
  );
}
