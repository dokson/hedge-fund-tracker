/**
 * The app's one polite status region (rendered once by the layout). Every announcement goes
 * through it: a page change, a table sorted. A second live region would talk over this one.
 */
export const APP_STATUS_ID = "app-status";

/**
 * Marks the status region every native modal carries: while a modal is open the page behind
 * it is inert, so the layout's region could not be heard.
 */
export const DIALOG_STATUS_ATTR = "data-dialog-status";

/** The region to speak through: the topmost open modal's, else the layout's. */
function statusRegion(): HTMLElement | null {
  if (typeof document === "undefined") return null;
  const dialogs = document.querySelectorAll<HTMLDialogElement>("dialog[open]");
  const top = dialogs[dialogs.length - 1];
  return (
    top?.querySelector<HTMLElement>(`[${DIALOG_STATUS_ATTR}]`) ??
    document.getElementById(APP_STATUS_ID)
  );
}

/**
 * Speak a short message to screen readers. The text is cleared first so the same message
 * twice in a row (sorting the same column back) is still announced.
 */
export function announce(message: string): void {
  const region = statusRegion();
  if (!region) return;
  region.textContent = "";
  window.setTimeout(() => {
    region.textContent = message;
  }, 50);
}

/** The message for a sorted column: its name and the new direction. */
export function sortMessage(label: string, direction: "asc" | "desc"): string {
  return `Sorted by ${label}, ${direction === "asc" ? "ascending" : "descending"}`;
}
