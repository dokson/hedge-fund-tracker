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

(
  globalThis as unknown as { IntersectionObserver: typeof IntersectionObserver }
).IntersectionObserver = SyncIntersectionObserver as unknown as typeof IntersectionObserver;
