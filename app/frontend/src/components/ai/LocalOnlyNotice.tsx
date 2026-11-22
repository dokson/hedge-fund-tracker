import type { ReactNode } from "react";

import { StatusChip } from "@/components/ui/StatusChip";
import { TextLink } from "@/components/ui/TextLink";

import { REPO_URL } from "@/lib/config";

export interface SampleStatus {
  /** What the sample is, e.g. "Sample ranking". */
  label: string;
  /** Quarter or ticker the sample was generated for. */
  subject?: string;
  generatedAt?: string;
}

interface LocalOnlyNoticeProps {
  /** Why this feature needs the local backend. */
  description: ReactNode;
  /** When set, a warning pill says the data shown is a canned sample. */
  sample?: SampleStatus | false;
}

/**
 * One line on the static site saying the analysis runs only locally, with the
 * sample's pill; the install steps live in the README the link opens.
 */
export default function LocalOnlyNotice({ description, sample }: LocalOnlyNoticeProps) {
  return (
    <section
      aria-labelledby="local-door-title"
      className="frame flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2 text-[13px]"
    >
      <h2 id="local-door-title" className="sr-only">
        Runs locally
      </h2>
      {sample && (
        <StatusChip tone="warning" className="max-w-full whitespace-normal sm:whitespace-nowrap">
          {sample.label}
          {sample.subject && <> for {sample.subject}</>}
          {sample.generatedAt && <>, generated {sample.generatedAt}</>}, not live
        </StatusChip>
      )}
      <p className="min-w-0 text-muted-foreground">
        {description} <TextLink href={REPO_URL}>Run it locally</TextLink>
      </p>
    </section>
  );
}
