/**
 * Spread on the control a native `<dialog>` should focus when it opens. It writes the real
 * `autofocus` attribute: React's `autoFocus` prop does not reach the DOM (React calls `focus()`
 * itself on mount, while the dialog is still closed, so it does nothing), and `showModal()`
 * would then focus the first focusable element instead. Per Modern Web Guidance `dialog`: the
 * primary field, or the safe action of a destructive confirmation.
 */
export const DIALOG_AUTOFOCUS = { autofocus: "" } as Record<string, string>;
