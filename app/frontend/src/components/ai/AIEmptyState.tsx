import { Sparkles } from "lucide-react";
import { EmptyState } from "@/components/ui/EmptyState";

interface AIEmptyStateProps {
  message: string;
}

/** Shared idle state for the two AI research pages. */
export default function AIEmptyState({ message }: AIEmptyStateProps) {
  return <EmptyState icon={Sparkles} title="Ready for analysis" description={message} />;
}
