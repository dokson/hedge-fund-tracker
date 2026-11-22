import { Moon, Sun } from "lucide-react";

import { cn } from "@/lib/utils";

/**
 * The light/dark switch in the top bar: a pill track with a sun and a moon, the thumb
 * resting on the scheme shown. It is one switch (`role="switch"`, checked = dark), so a
 * click, Space or Enter flips it and assistive tech reads the state, not two buttons.
 */
export function ThemeSwitch({
  isDark,
  onToggle,
  className,
}: {
  isDark: boolean;
  onToggle: () => void;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={isDark}
      aria-label="Dark theme"
      title={isDark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={onToggle}
      className={cn(
        "relative inline-flex h-8 w-[60px] shrink-0 items-center rounded-full border border-input bg-muted p-0.5 transition-colors duration-[120ms] hover:border-muted-foreground active:bg-secondary",
        className,
      )}
    >
      {/* The thumb slides with transform only, and jumps when the OS asks for less motion. */}
      <span
        aria-hidden="true"
        className={cn(
          "absolute left-0.5 top-0.5 h-[26px] w-[26px] rounded-full bg-card shadow-sm ring-1 ring-input transition-transform duration-200 ease-out motion-reduce:transition-none",
          isDark && "translate-x-[28px]",
        )}
      />
      <span aria-hidden="true" className="relative z-10 grid w-[26px] place-items-center">
        <Sun className={cn("h-3.5 w-3.5", isDark ? "text-muted-foreground" : "text-gold-text")} />
      </span>
      <span aria-hidden="true" className="relative z-10 ml-0.5 grid w-[26px] place-items-center">
        <Moon
          className={cn("h-3.5 w-3.5", isDark ? "text-primary-text" : "text-muted-foreground")}
        />
      </span>
    </button>
  );
}
