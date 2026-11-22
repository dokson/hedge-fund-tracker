import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import { announce } from "@/lib/announce";

type ToastItem = {
  id: number;
  message: string;
  description?: string;
  previousFocus: HTMLElement | null;
};

type ToastOptions = { description?: string };

let nextId = 0;
let items: ToastItem[] = [];
let pending: ToastItem[] = [];
const listeners = new Set<() => void>();

function publish() {
  listeners.forEach((listener) => listener());
}

function hasOpenModal() {
  return Array.from(document.querySelectorAll("dialog[open]")).some((dialog) => {
    try {
      return dialog.matches(":modal");
    } catch {
      return true;
    }
  });
}

function deliverPending() {
  if (!pending.length || hasOpenModal()) return;
  const delivered = pending;
  pending = [];
  items = [...items, ...delivered];
  publish();
  announce(delivered.map(({ message, description }) =>
    description ? `${message}. ${description}` : message,
  ).join(". "));
}

function addToast(message: string, options?: ToastOptions) {
  const id = ++nextId;
  pending.push({
    id,
    message,
    description: options?.description,
    previousFocus: document.activeElement instanceof HTMLElement ? document.activeElement : null,
  });
  deliverPending();
  return id;
}

function dismissToast(id: number) {
  items = items.filter((item) => item.id !== id);
  publish();
}

const toast = {
  success: addToast,
  error: addToast,
};

/** Displays a notification and pauses its expiry while it is being used. */
function Toast({ item }: { item: ToastItem }) {
  const ref = useRef<HTMLDivElement>(null);
  const remaining = useRef(4000);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    if (hovered || focused) return;
    const started = Date.now();
    const timer = window.setTimeout(() => dismissToast(item.id), remaining.current);
    return () => {
      window.clearTimeout(timer);
      remaining.current = Math.max(0, remaining.current - (Date.now() - started));
    };
  }, [focused, hovered, item.id]);

  function dismiss() {
    const element = ref.current;
    if (element?.contains(document.activeElement)) {
      const next = element.nextElementSibling ?? element.previousElementSibling;
      const button = next?.querySelector<HTMLButtonElement>("button");
      if (button) button.focus();
      else if (item.previousFocus?.isConnected) item.previousFocus.focus();
    }
    dismissToast(item.id);
  }

  return (
    <div
      ref={ref}
      className="flex items-start gap-3 rounded-md border border-border bg-popover p-4 text-sm text-popover-foreground shadow-md"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onFocus={() => setFocused(true)}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setFocused(false);
      }}
    >
      <div className="min-w-0 flex-1 break-words">
        <div className="font-medium">{item.message}</div>
        {item.description && <div className="mt-1 text-muted-foreground">{item.description}</div>}
      </div>
      <button
        type="button"
        aria-label="Dismiss notification"
        className="shrink-0 rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
        onClick={dismiss}
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  );
}

/** Hosts the notification stack in a single manual top-layer popover. */
function Toaster() {
  const [toasts, setToasts] = useState(items);
  const ref = useRef<HTMLDivElement>(null);
  const isOpen = useRef(false);

  useEffect(() => {
    const update = () => setToasts(items);
    listeners.add(update);
    update();
    const observer = new MutationObserver(deliverPending);
    observer.observe(document.body, { attributes: true, attributeFilter: ["open"], childList: true, subtree: true });
    deliverPending();
    return () => {
      observer.disconnect();
      listeners.delete(update);
    };
  }, []);

  useEffect(() => {
    const element = ref.current;
    if (!element || typeof element.showPopover !== "function") return;
    if (toasts.length && !isOpen.current) {
      element.showPopover();
      isOpen.current = true;
    } else if (!toasts.length && isOpen.current) {
      element.hidePopover();
      isOpen.current = false;
    }
  }, [toasts.length]);

  return (
    <div
      ref={ref}
      popover="manual"
      role="region"
      aria-label="Notifications"
      className="fixed inset-auto right-4 bottom-4 m-0 max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-sm overflow-y-auto border-0 bg-transparent p-0"
      style={typeof HTMLElement !== "undefined" && !("popover" in HTMLElement.prototype) && !toasts.length ? { display: "none" } : undefined}
    >
      <div className="flex flex-col gap-2">
        {toasts.map((item) => <Toast key={item.id} item={item} />)}
      </div>
    </div>
  );
}

export { Toaster, toast };
