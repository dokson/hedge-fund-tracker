import type { ReactNode } from "react";

import { TableFrame } from "@/components/ui/TableFrame";
import { Panel } from "@/components/ui/Panel";
import { StatusChip } from "@/components/ui/StatusChip";
import { TextLink } from "@/components/ui/TextLink";

export const REPO_URL = "https://github.com/dokson/hedge-fund-tracker";

const INSTALL_STEPS = [`git clone ${REPO_URL}.git`, "pipenv install", "pipenv run app"];

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

/** Explain local-only analysis while keeping saved samples clearly labelled. */
export default function LocalOnlyNotice({ description, sample }: LocalOnlyNoticeProps) {
  return (
    <Panel
      title="Runs locally"
      titleId="local-door-title"
      headerClassName="grid h-auto min-h-9 grid-cols-1 items-start gap-y-1 py-1.5 sm:flex sm:flex-nowrap sm:items-center sm:justify-between sm:py-0"
      aside={
        sample && (
          <StatusChip
            role="status"
            tone="warning"
            className="max-w-full whitespace-normal sm:whitespace-nowrap"
          >
            {sample.label}
            {sample.subject && <> · {sample.subject}</>}
            {sample.generatedAt && <> · generated {sample.generatedAt}</>} · not live
          </StatusChip>
        )
      }
    >
      <div className="space-y-3 p-3">
        <p className="max-w-[70ch] text-[13px] leading-6 text-muted-foreground">{description}</p>
        {/* Install steps are a desktop instruction: nobody clones a repo from a
            phone, and the commands only cost scroll there. The reason the
            feature is unavailable, and the sample pill above it, stay. */}
        {/* A <pre> that scrolls is a scroll container a keyboard-only visitor
            cannot pan (SC 2.1.1); TableFrame makes it a named, focusable one. */}
        <TableFrame
          label="Install commands"
          className="hidden rounded-sm border border-border bg-background md:block"
        >
          <pre className="p-3 text-xs leading-6">
            {INSTALL_STEPS.map((cmd) => `$ ${cmd}`).join("\n")}
          </pre>
        </TableFrame>
        <p className="hidden text-xs text-muted-foreground md:block">
          Bring your own API key; the README lists the supported providers.{" "}
          <TextLink href={REPO_URL}>View on GitHub</TextLink>
        </p>
      </div>
    </Panel>
  );
}
