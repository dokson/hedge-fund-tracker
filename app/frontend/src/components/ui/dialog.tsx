import * as React from "react";
import { createPortal } from "react-dom";
import { Slot } from "@radix-ui/react-slot";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { PortalContainerContext } from "@/lib/portalContainer";
import { DIALOG_STATUS_ATTR } from "@/lib/announce";

type DialogContextValue = {
  open: boolean;
  setOpen: (open: boolean) => void;
  titleId: string;
  descriptionId: string;
};

const DialogContext = React.createContext<DialogContextValue | null>(null);

function useDialog() {
  const context = React.useContext(DialogContext);
  if (!context) throw new Error("Dialog components must be inside Dialog");
  return context;
}

/** Shares controlled or uncontrolled state and accessible IDs with the native modal. */
function Dialog({
  open,
  defaultOpen = false,
  onOpenChange,
  children,
}: {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: React.ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  const [internalOpen, setInternalOpen] = React.useState(defaultOpen);
  const titleId = React.useId();
  const descriptionId = React.useId();
  const setOpen = React.useCallback(
    (next: boolean) => {
      if (open === undefined) setInternalOpen(next);
      onOpenChange?.(next);
    },
    [open, onOpenChange],
  );
  return (
    <DialogContext.Provider
      value={{ open: open ?? internalOpen, setOpen, titleId, descriptionId }}
    >
      {children}
    </DialogContext.Provider>
  );
}

const DialogPortal = ({ children }: { children?: React.ReactNode }) =>
  typeof document === "undefined"
    ? null
    : createPortal(children, document.body);

const DialogOverlay = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => (
  <div ref={ref} className={className} {...props} />
));
DialogOverlay.displayName = "DialogOverlay";

type DialogButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  asChild?: boolean;
};
const DialogTrigger = React.forwardRef<HTMLButtonElement, DialogButtonProps>(
  ({ asChild, onClick, ...props }, ref) => {
    const { setOpen } = useDialog();
    const Component = asChild ? Slot : "button";
    return (
      <Component
        ref={ref}
        {...props}
        onClick={(event) => {
          onClick?.(event);
          if (!event.defaultPrevented) setOpen(true);
        }}
      />
    );
  },
);
DialogTrigger.displayName = "DialogTrigger";

const DialogClose = React.forwardRef<HTMLButtonElement, DialogButtonProps>(
  ({ asChild, onClick, ...props }, ref) => {
    const { setOpen } = useDialog();
    const Component = asChild ? Slot : "button";
    return (
      <Component
        ref={ref}
        type="button"
        {...props}
        onClick={(event) => {
          onClick?.(event);
          if (!event.defaultPrevented) setOpen(false);
        }}
      />
    );
  },
);
DialogClose.displayName = "DialogClose";

// Safari ships <dialog> without `closedby`: there the backdrop click and the "none" policy
// are applied by hand below.
const supportsClosedBy = typeof HTMLDialogElement !== "undefined" && "closedBy" in HTMLDialogElement.prototype;

/** A click on the dialog element itself outside its box is a click on the backdrop. */
function isBackdropClick(event: React.MouseEvent<HTMLDialogElement>): boolean {
  const dialog = event.currentTarget;
  if (event.target !== dialog) return false;
  const rect = dialog.getBoundingClientRect();
  return (
    event.clientY < rect.top ||
    event.clientY > rect.bottom ||
    event.clientX < rect.left ||
    event.clientX > rect.right
  );
}

type DialogContentProps = React.DialogHTMLAttributes<HTMLDialogElement> & {
  showCloseButton?: boolean;
  closedBy?: "any" | "closerequest" | "none";
};

/** Opens a native modal and synchronizes browser close requests with React state. */
const DialogContent = React.forwardRef<HTMLDialogElement, DialogContentProps>(
  (
    {
      className,
      children,
      showCloseButton = true,
      closedBy = "any",
      onClose,
      onClick,
      onCancel,
      ...props
    },
    forwardedRef,
  ) => {
    const { open, setOpen, titleId, descriptionId } = useDialog();
    const ref = React.useRef<HTMLDialogElement>(null);
    // The mounted dialog, as state: floating layers inside it (select menus, tooltips) portal
    // here, since outside a modal is inert and below the top layer.
    const [node, setNode] = React.useState<HTMLDialogElement | null>(null);
    const setRefs = React.useCallback((element: HTMLDialogElement | null) => {
      ref.current = element;
      setNode(element);
    }, []);
    React.useImperativeHandle(forwardedRef, () => ref.current!);
    React.useLayoutEffect(() => {
      const dialog = ref.current;
      if (!dialog) return;
      if (open && !dialog.open) dialog.showModal();
      else if (!open && dialog.open) dialog.close();
    }, [open]);
    return (
      <DialogPortal>
        <dialog
          ref={setRefs}
          aria-labelledby={titleId}
          aria-describedby={descriptionId}
          {...{ closedby: closedBy }}
          className={cn(
            "fixed inset-0 m-auto max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-xl border border-border bg-popover p-6 text-foreground shadow-xl open:grid open:gap-4 [&:modal]:overscroll-contain backdrop:bg-black/60 backdrop:overflow-hidden backdrop:overscroll-contain opacity-0 open:opacity-100 starting:open:opacity-0 transition-[opacity,display,overlay] transition-discrete duration-150 motion-reduce:duration-0",
            className,
          )}
          {...props}
          onClick={(event) => {
            onClick?.(event);
            if (!supportsClosedBy && closedBy === "any" && isBackdropClick(event)) {
              event.currentTarget.close();
            }
          }}
          onCancel={(event) => {
            onCancel?.(event);
            if (!supportsClosedBy && closedBy === "none") event.preventDefault();
          }}
          onClose={(event) => {
            onClose?.(event);
            if (open) setOpen(false);
          }}
        >
          {/* Written by `announce()` while this modal is open; empty React children so a
              re-render never wipes it. */}
          <div {...{ [DIALOG_STATUS_ATTR]: "" }} role="status" className="sr-only" />
          <PortalContainerContext.Provider value={node}>
            {open && children}
          </PortalContainerContext.Provider>
          {open && showCloseButton && (
            <DialogClose asChild>
              <Button
                variant="ghost"
                size="icon"
                className="absolute right-2 top-2 h-8 w-8"
              >
                <X className="h-4 w-4" aria-hidden="true" />
                <span className="sr-only">Close</span>
              </Button>
            </DialogClose>
          )}
        </dialog>
      </DialogPortal>
    );
  },
);
DialogContent.displayName = "DialogContent";

const DialogHeader = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col space-y-1.5 text-center sm:text-left",
      className,
    )}
    {...props}
  />
);
const DialogFooter = ({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) => (
  <div
    className={cn(
      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
      className,
    )}
    {...props}
  />
);
const DialogTitle = React.forwardRef<
  HTMLHeadingElement,
  React.HTMLAttributes<HTMLHeadingElement>
>(({ className, id, ...props }, ref) => {
  const { titleId } = useDialog();
  return (
    <h2
      ref={ref}
      id={id ?? titleId}
      className={cn("section-title", className)}
      {...props}
    />
  );
});
DialogTitle.displayName = "DialogTitle";
const DialogDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, id, ...props }, ref) => {
  const { descriptionId } = useDialog();
  return (
    <p
      ref={ref}
      id={id ?? descriptionId}
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
});
DialogDescription.displayName = "DialogDescription";

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
};
