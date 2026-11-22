import type { ReactNode } from "react";

import { StatusChip } from "@/components/ui/StatusChip";
import { changeLabel, changeTone } from "@/lib/tone";

/**
 * The chip for a position-change token from the data (NEW, INCREASE, DECREASE, CLOSE, CLOSED,
 * NO CHANGE): its tone (buys green, sales red) and its sentence-case label, the one way every
 * table, card and feed draws a change. `suffix` appends a figure (e.g. " +12%").
 */
export function ChangeChip({
  change,
  suffix,
  className,
}: {
  change: string;
  suffix?: ReactNode;
  className?: string;
}) {
  return (
    <StatusChip tone={changeTone(change)} className={className}>
      {changeLabel(change)}
      {suffix}
    </StatusChip>
  );
}
