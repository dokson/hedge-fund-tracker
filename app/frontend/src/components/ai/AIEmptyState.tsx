import { Brain } from "lucide-react";

interface AIEmptyStateProps {
  message: string;
}

export default function AIEmptyState({ message }: AIEmptyStateProps) {
  return (
    <div className="rounded-lg border border-border bg-card p-12 text-center">
      <Brain className="h-12 w-12 text-muted-foreground mx-auto mb-4 opacity-30" />
      <p className="text-muted-foreground">{message}</p>
    </div>
  );
}
