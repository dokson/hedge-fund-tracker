import { LoadingState } from "@/components/ui/LoadingState";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

/**
 * Loader for a progress-reporting analysis. Until the first progress tick it
 * stays indeterminate: an observer that joins an in-flight fetch never
 * receives the callbacks, so a 0% bar would sit there frozen.
 */
export function AnalysisProgress({
  msg,
  pct,
  className,
}: {
  msg: string;
  pct: number;
  className?: string;
}) {
  const started = pct > 0;
  return (
    <div className={cn("flex flex-col items-center gap-3", className)}>
      <LoadingState
        size="sm"
        className="py-0"
        message={started && msg ? msg : "Loading analysis…"}
      />
      {started && <Progress value={pct} className="w-64" />}
    </div>
  );
}
