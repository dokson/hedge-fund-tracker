/**
 * Shared vitest setup. Polyfills DOM APIs that jsdom doesn't ship (e.g.
 * IntersectionObserver) so every test file can rely on them without
 * boilerplate.
 *
 * Wired in via `test.setupFiles` in vite.config.ts.
 */
// Synchronous IntersectionObserver: fires `isIntersecting=true` on observe()
// so components gated by intersection (CompanyLogo, FundLogo) render their
// content immediately in tests.
class SyncIntersectionObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "";
  readonly scrollMargin = "";
  readonly thresholds: readonly number[] = [];
  private callback: IntersectionObserverCallback;

  constructor(cb: IntersectionObserverCallback) {
    this.callback = cb;
  }

  observe(target: Element): void {
    this.callback([{ isIntersecting: true, target } as IntersectionObserverEntry], this);
  }
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

// A permanent polyfill, not `vi.stubGlobal`: a test that resets its own stubs with
// `vi.unstubAllGlobals()` would otherwise delete it for every later test in the file.
globalThis.IntersectionObserver = SyncIntersectionObserver;

// jsdom does not implement the top-layer APIs. Keep their observable state and
// basic focus behavior available to components that use native dialogs/popovers.
if (!HTMLDialogElement.prototype.showModal) {
  const openers = new WeakMap<HTMLDialogElement, HTMLElement>();
  const inertStates = new WeakMap<HTMLDialogElement, Map<HTMLElement, boolean>>();
  let lastOutsideFocus: HTMLElement | null = null;
  document.addEventListener("focusin", (event) => {
    const target = event.target;
    if (target instanceof HTMLElement && !target.closest("dialog:not([open])")) {
      lastOutsideFocus = target;
    }
  });

  HTMLDialogElement.prototype.showModal = function () {
    if (this.open) return;
    const focused = document.activeElement;
    const opener =
      focused instanceof HTMLElement && !this.contains(focused) ? focused : lastOutsideFocus;
    if (opener) openers.set(this, opener);
    this.open = true;
    const states = new Map<HTMLElement, boolean>();
    for (const element of document.body.querySelectorAll<HTMLElement>("*")) {
      if (element === this || element.contains(this) || this.contains(element)) continue;
      states.set(element, !!element.inert);
      element.inert = true;
    }
    inertStates.set(this, states);
    const initialFocus =
      this.querySelector<HTMLElement>("[autofocus]") ??
      this.querySelector<HTMLElement>(
        "button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])",
      );
    (initialFocus ?? this).focus();
  };

  HTMLDialogElement.prototype.close = function (returnValue?: string) {
    if (!this.open) return;
    if (returnValue !== undefined) this.returnValue = returnValue;
    this.open = false;
    for (const [element, inert] of inertStates.get(this) ?? []) element.inert = inert;
    inertStates.delete(this);
    this.dispatchEvent(new Event("close"));
    openers.get(this)?.focus();
    openers.delete(this);
  };

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    const dialogs = document.querySelectorAll<HTMLDialogElement>("dialog[open]");
    const dialog = dialogs[dialogs.length - 1];
    if (dialog && dialog.dispatchEvent(new Event("cancel", { cancelable: true }))) {
      dialog.close();
    }
  });
}

if (!HTMLElement.prototype.showPopover) {
  HTMLElement.prototype.showPopover = function () {
    if (this.classList.contains(":popover-open")) return;
    this.classList.add(":popover-open");
    this.dispatchEvent(new Event("toggle"));
  };
  HTMLElement.prototype.hidePopover = function () {
    if (!this.classList.contains(":popover-open")) return;
    this.classList.remove(":popover-open");
    this.dispatchEvent(new Event("toggle"));
  };
  HTMLElement.prototype.togglePopover = function (force?: boolean) {
    const open = force ?? !this.classList.contains(":popover-open");
    if (open) this.showPopover();
    else this.hidePopover();
    return open;
  };
}
