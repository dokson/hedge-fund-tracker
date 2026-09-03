import { useState } from "react";

export const MOBILE_NOTICE_KEY = "hft:mobile-notice-dismissed";

/** Reads the flag defensively: private mode and blocked site data both throw. */
function alreadyDismissed(): boolean {
  try {
    return sessionStorage.getItem(MOBILE_NOTICE_KEY) === "1";
  } catch {
    return false;
  }
}

/**
 * A one-line, once-per-session heads-up on phones that the board is laid out
 * for a wider screen. `hidden md:hidden`-style responsive gating only, so the
 * markup is identical on every render and the static /learn pre-render (built
 * from FAQ strings, not from React) is untouched.
 *
 * The dismissal is read during the first render rather than in an effect, so a
 * visitor who already dismissed it never sees the row appear and collapse.
 */
export default function MobileNotice() {
  const [visible, setVisible] = useState(() => !alreadyDismissed());

  if (!visible) return null;

  return (
    <div
      role="status"
      className="flex shrink-0 items-start gap-3 border-b border-border bg-muted px-3 py-2 text-[13px] leading-5 text-muted-foreground md:hidden"
    >
      <p className="min-w-0 flex-1">Best on a wider screen: tables and charts are denser there.</p>
      <button
        type="button"
        onClick={() => {
          try {
            sessionStorage.setItem(MOBILE_NOTICE_KEY, "1");
          } catch {
            // A blocked store only costs the visitor a second dismissal.
          }
          setVisible(false);
        }}
        className="-my-0.5 h-6 shrink-0 rounded px-2 text-[13px] font-medium text-foreground transition-colors duration-[120ms] hover:bg-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Got it
      </button>
    </div>
  );
}
