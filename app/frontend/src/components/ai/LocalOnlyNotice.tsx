import type { ReactNode } from "react";

import { TableFrame } from "@/components/ui/TableFrame";

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

/**
 * The AI features are local-only: this panel says so and sells the three-line
 * install instead of apologising for the gap.
 */
export default function LocalOnlyNotice({ description, sample }: LocalOnlyNoticeProps) {
  return (
    <section className="frame" aria-labelledby="local-door-title">
      {/* The status pill is one long nowrap line: on a phone it overflowed the
          fixed-height title row, so below `sm` the row wraps and the pill wraps
          with it. */}
      <div className="frame-title h-auto min-h-9 flex-wrap justify-start gap-y-1 py-1.5 sm:flex-nowrap sm:justify-between sm:py-0">
        <h2 id="local-door-title" className="text-magenta">
          Runs locally
        </h2>
        {sample && (
          <span
            className="chip max-w-full whitespace-normal text-warning sm:whitespace-nowrap"
            role="status"
          >
            {sample.label}
            {sample.subject && <> · {sample.subject}</>}
            {sample.generatedAt && <> · generated {sample.generatedAt}</>} · not live
          </span>
        )}
      </div>
      <div className="space-y-3 p-3">
        <p className="max-w-[64ch] text-[13px] text-muted-foreground">{description}</p>
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
          <a
            href={REPO_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-text hover:underline"
          >
            View on GitHub
          </a>
        </p>
      </div>
    </section>
  );
}
