import { Sparkles } from "lucide-react";

interface AIEmptyStateProps {
  message: string;
}

/** The AI door's idle screen. */
export default function AIEmptyState({ message }: AIEmptyStateProps) {
  return (
    <div className="frame flex flex-col items-center gap-2 px-6 py-10 text-center">
      <Sparkles className="h-5 w-5 text-magenta" aria-hidden="true" />
      <p className="text-[13px] text-muted-foreground">{message}</p>
    </div>
  );
}
