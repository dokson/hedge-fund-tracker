import { Brain } from "lucide-react";
import type { ReactNode } from "react";

interface LocalOnlyNoticeProps {
  /**
   * Short description of what the feature does and why it needs the backend.
   */
  description: ReactNode;
  /**
   * Optional extra content rendered after the description (e.g. a "sample
   * output for X generated on Y" sentence).
   */
  sampleNote?: ReactNode;
}

export default function LocalOnlyNotice({ description, sampleNote }: LocalOnlyNoticeProps) {
  return (
    <div className="rounded-lg border border-blue-200 bg-blue-50/50 dark:bg-blue-950/20 dark:border-blue-800 px-4 py-3">
      <p className="text-sm font-semibold text-blue-700 dark:text-blue-300 flex items-center gap-2">
        <Brain className="h-4 w-4" /> Local-Only Feature
      </p>
      <p className="text-xs text-blue-600/80 dark:text-blue-400/80 leading-relaxed mt-1">
        {description}
        {sampleNote && (
          <>
            <br />
            {sampleNote}
          </>
        )}
      </p>
    </div>
  );
}
