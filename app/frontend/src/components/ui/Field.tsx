import type { ReactNode } from "react";

import { InfoTooltip } from "@/components/ui/InfoTooltip";
import { cn } from "@/lib/utils";

interface FieldProps {
  label: ReactNode;
  /** Id of the control the label names; without it the label is plain text above it. */
  htmlFor?: string;
  info?: string;
  /** Hide the label on phones when the value already describes itself. */
  labelHiddenOnMobile?: boolean;
  className?: string;
  children: ReactNode;
}

/** A small label above its control: the one form-field shape used in bands, dialogs and settings. */
export function Field({
  label,
  htmlFor,
  info,
  labelHiddenOnMobile = false,
  className,
  children,
}: FieldProps) {
  const labelClass = cn(
    "metric-label flex h-4 items-center gap-1",
    labelHiddenOnMobile && "max-sm:hidden",
  );
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      {htmlFor ? (
        <label htmlFor={htmlFor} className={labelClass}>
          {label}
          {info && <InfoTooltip text={info} />}
        </label>
      ) : (
        <span className={labelClass}>
          {label}
          {info && <InfoTooltip text={info} />}
        </span>
      )}
      {children}
    </div>
  );
}

/**
 * The ruled band of fields above a result (observation scope, analysis inputs).
 * `label` names the section for assistive tech; layout overrides go in `className`.
 */
export function ControlBand({
  label,
  className,
  children,
}: {
  label: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section
      aria-label={label}
      className={cn(
        "flex flex-wrap items-end gap-x-6 gap-y-3 border-y border-border py-3",
        className,
      )}
    >
      {children}
    </section>
  );
}
